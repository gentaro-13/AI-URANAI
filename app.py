from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, RichMenuRequest, RichMenuArea, RichMenuSize, RichMenuBounds, PostbackAction, MessageAction, QuickReply, QuickReplyItem, FlexMessage, FlexContainer
from linebot.v3.webhooks import MessageEvent, TextMessageContent, PostbackEvent, FollowEvent, UnfollowEvent
import os
from dotenv import load_dotenv
import urllib3
import re
from datetime import datetime, timedelta
from openai import OpenAI
import ssl
import certifi
import redis
import json
import requests
from db import save_msg, fetch_recent, save_profile, get_profile

# .envファイルから環境変数を読み込む
load_dotenv()

# LINE Botの設定
configuration = Configuration(
    access_token=os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
)

# SSL証明書の設定
ssl_context = ssl.create_default_context(cafile=certifi.where())
configuration.ssl_ca_certs = certifi.where()

# Redisの設定
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=0,
    decode_responses=True
)

app = Flask(__name__)
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

# OpenAI APIの設定
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# ユーザ状態をメモリで保持（本番は DB 推奨）
user_states: dict[str, dict] = {}
user_birthdates = {}

def get_user_state(user_id):
    """ユーザーの状態を取得"""
    return user_states.get(user_id, {"stage": None})

def set_user_state(user_id, state):
    """ユーザーの状態を設定"""
    user_states[user_id] = state

def get_user_birthdate(user_id):
    """ユーザーの生年月日を取得"""
    return user_birthdates.get(user_id)

def set_user_birthdate(user_id, birthdate):
    """ユーザーの生年月日を設定"""
    user_birthdates[user_id] = birthdate

def create_rich_menu():
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        
        # 既存のリッチメニュー一覧を取得
        rich_menus = line_bot_api.get_rich_menu_list()
        
        # 既存のリッチメニューを削除
        for menu in rich_menus.richmenus:
            try:
                line_bot_api.delete_rich_menu(menu.rich_menu_id)
            except Exception as e:
                print(f"リッチメニューの削除に失敗しました: {e}")
        
        # 新しいリッチメニューの作成
        rich_menu = RichMenuRequest(
            size=RichMenuSize(width=2500, height=843),
            selected=True,
            name="占いメニュー",
            chat_bar_text="占いを始めましょう",
            areas=[
                RichMenuArea(
                    bounds=RichMenuBounds(x=0, y=0, width=1250, height=843),
                    action=MessageAction(text="占い")
                ),
                RichMenuArea(
                    bounds=RichMenuBounds(x=1250, y=0, width=1250, height=843),
                    action=PostbackAction(data="help", display_text="ヘルプ")
                )
            ]
        )
        
        rich_menu_id = line_bot_api.create_rich_menu(rich_menu).rich_menu_id
        print(f"✅ リッチメニューを作成しました: {rich_menu_id}")
        
        # リッチメニューの画像をアップロード
        try:
            with open("rich_menu.png", 'rb') as f:
                url = f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content"
                headers = {
                    "Authorization": f"Bearer {os.getenv('LINE_CHANNEL_ACCESS_TOKEN')}",
                    "Content-Type": "image/png"
                }
                response = requests.post(url, headers=headers, data=f.read())
                if response.status_code == 200:
                    print("✅ リッチメニュー画像をアップロードしました")
                else:
                    print(f"❌ リッチメニュー画像のアップロードに失敗しました: {response.text}")
                    return None
            
            # リッチメニューをデフォルトに設定
            line_bot_api.set_default_rich_menu(rich_menu_id)
            print("✅ リッチメニューをデフォルトに設定しました")
            return rich_menu_id
        except Exception as e:
            print(f"❌ リッチメニューの設定に失敗しました: {e}")
            # エラーが発生した場合はリッチメニューを削除
            line_bot_api.delete_rich_menu(rich_menu_id)
            return None

def is_valid_date(date_str):
    try:
        datetime.strptime(date_str, '%Y/%m/%d')
        return True
    except ValueError:
        return False

def get_birthday_reading(birthdate):
    """生年月日から占いの解釈を生成"""
    prompt = f"""
    以下の情報に基づいて、占いの解釈を生成してください：
    
    生年月日: {birthdate}
    現在の日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    
    この情報から、その人の運勢やアドバイスを、以下の形式で出力してください：
    1. 全体的な運勢
    2. 仕事・キャリア
    3. 恋愛・人間関係
    4. 健康
    5. 今日のアドバイス
    
    各項目は簡潔に、具体的なアドバイスを含めてください。
    """
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "あなたはプロの占い師です。正確で具体的な占いの解釈を提供してください。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=500
    )
    
    return response.choices[0].message.content

def love_advice(text: str) -> str:
    """恋愛相談テキストを OpenAI で要約 & アドバイス生成"""
    prompt = (
        open("prompts/system.md", encoding="utf-8").read()
        + f"\n\n【ユーザーの悩み】\n{text.strip()}\n\n---\n"
        "上記を踏まえて 3〜5 行で回答してください。"
    )
    res = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "あなたはプロの占星術師です。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.8,
        max_tokens=400,
    )
    return res.choices[0].message.content.strip()

def send(api: MessagingApi, token: str, text: str,
         quick: list[QuickReplyItem] | None = None):
    api.reply_message_with_http_info(
        ReplyMessageRequest(
            reply_token=token,
            messages=[TextMessage(text=text, quick_reply=QuickReply(items=quick) if quick else None)]
        )
    )

# ----------------------------------------
# 1) FollowEvent  ─ 友だち追加あいさつ
# ----------------------------------------

@handler.add(FollowEvent)
def handle_follow(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        try:
            # プロフィール情報を取得
            profile = line_bot_api.get_profile(event.source.user_id)
            user_name = profile.display_name
            
            # ウェルカムメッセージを送信
            welcome_message = f"{user_name}さん、こんにちは！\nオーラ診断へようこそ。\n\n生年月日を入力して、あなたのオーラを診断しましょう。\n例：1988/11/16"
            
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=welcome_message)]
                )
            )
        except Exception as e:
            print(f"Error in handle_follow: {str(e)}")
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="申し訳ありません。エラーが発生しました。もう一度お試しください。")]
                )
            )

# ----------------------------------------
# 2) 以降の Message / Postback ハンドリング
# ----------------------------------------

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        try:
            message_text = event.message.text
            user_id = event.source.user_id
            
            # 日付形式のチェック
            if is_valid_date(message_text):
                # 日付をISO形式に変換
                date_iso = message_text.replace('/', '-')
                result = get_birthday_reading(date_iso)
                
                if result:
                    # オーラ診断結果を送信
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=result)]
                        )
                    )
                else:
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="申し訳ありません。占いの結果を取得できませんでした。もう一度お試しください。")]
                        )
                    )
            else:
                # 自由会話のレスポンス
                response = love_advice(message_text)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=response)]
                    )
                )
        except Exception as e:
            print(f"Error in handle_message: {str(e)}")
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="申し訳ありません。エラーが発生しました。もう一度お試しください。")]
                )
            )

# ----------------------------------------
# 3) DateTimePicker のポストバックを受け取る
# ----------------------------------------

@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data
    params = event.postback.params

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        
        if data == "birthdate_picker":
            if "date" in params:
                birthdate = params["date"].replace("-", "/")  # YYYY-MM-DD を YYYY/MM/DD に変換
                # 生年月日を保存
                save_profile(user_id, birthdate=birthdate)
                
                try:
                    result = get_birthday_reading(birthdate)
                    send(line_bot_api, event.reply_token, result)
                    set_user_state(user_id, None)
                except Exception as e:
                    print(f"Error in get_birthday_reading: {str(e)}")
                    send(line_bot_api, event.reply_token, "申し訳ありません。占いの結果を取得できませんでした。")
            else:
                quick_reply_items = [
                    QuickReplyItem(
                        action=PostbackAction(
                            data="birthdate_picker",
                            label="生年月日を選択",
                            display_text="生年月日を選択",
                            mode="date",
                            initial="2000-01-01",
                            max="2025-12-31",
                            min="1900-01-01"
                        )
                    )
                ]
                send(line_bot_api, event.reply_token, "生年月日を選択してください", quick_reply_items)

# ----------------------------------------
# 4) ChatGPT による占い生成ロジック
# ----------------------------------------

def run_aura(gender: str, birth: str) -> str:
    prompt = (
        f"あなたは熟練のスピリチュアルカウンセラーです。\n"
        f"次の入力をもとにオーラ診断を行い、各項目4行以内・矛盾なしで回答してください。\n\n"
        f"#性別: {gender}\n"
        f"#生年月日: {birth}\n\n"
        "フォーマット:\n"
        "1. オーラの色\n"
        "2. 今週の恋愛運\n"
        "3. 今週の金運\n"
        "4. 今週の健康運\n"
        "5. ラッキーアイテム\n"
        "6. 注意すること"
    )
    rsp = client.chat.completions.create(
        model="gpt-3.5-turbo",  # 予算が許せば gpt-4o-mini
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=500
    )
    return rsp.choices[0].message.content.strip()

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except Exception as e:
        app.logger.error(f"Error: {str(e)}")
        abort(400)

    return 'OK'

if __name__ == "__main__":
    # リッチメニューの作成
    create_rich_menu()
    app.run(host='0.0.0.0', port=8000) 