import os, json
from dotenv import load_dotenv; load_dotenv()
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi
from linebot.v3.messaging.models import (
    RichMenuRequest, RichMenuSize, RichMenuArea, RichMenuBounds,
    MessageAction, PostbackAction
)
import requests

conf = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
with ApiClient(conf) as cli:
    api = MessagingApi(cli)

    rich_req = RichMenuRequest(
        size=RichMenuSize(width=2500, height=843),
        selected=True,
        name="uranai_menu",
        chat_bar_text="占いを始める",
        areas=[
            # 左：占いスタート
            RichMenuArea(
                bounds=RichMenuBounds(x=0, y=0, width=1250, height=843),
                action=MessageAction(text="占い")
            ),
            # 右：使い方
            RichMenuArea(
                bounds=RichMenuBounds(x=1250, y=0, width=1250, height=843),
                action=PostbackAction(data="help", display_text="ヘルプを見る")
            )
        ]
    )

    rich_menu = api.create_rich_menu(rich_req)
    rich_id = rich_menu.rich_menu_id
    print("✅ RichMenu ID:", rich_id)

    # 画像をアップロード
    with open("rich_menu.png", "rb") as f:
        url = f"https://api-data.line.me/v2/bot/richmenu/{rich_id}/content"
        headers = {
            "Authorization": f"Bearer {os.getenv('LINE_CHANNEL_ACCESS_TOKEN')}",
            "Content-Type": "image/png"
        }
        image_data = f.read()
        print(f"画像サイズ: {len(image_data)} bytes")
        response = requests.post(url, headers=headers, data=image_data)
        print(f"ステータスコード: {response.status_code}")
        print(f"レスポンスヘッダー: {response.headers}")
        if response.status_code == 200:
            print("✅ リッチメニュー画像をアップロードしました")
        else:
            print("❌ リッチメニュー画像のアップロードに失敗しました")
            print(f"エラーレスポンス: {response.text}")
            exit(1)

    # デフォルトに設定
    api.set_default_rich_menu(rich_id)
    print("✅ リッチメニューをデフォルトに設定しました") 