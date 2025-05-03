import os, json, sys
from dotenv import load_dotenv
from openai import OpenAI
from engine import get_chart
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# データの読み込み
DF = pd.read_pickle("faq.pkl")
vectors = np.load("faq_vectors.npy")

def get_embedding(text):
    """OpenAI Embeddings APIを使用してテキストのベクトルを取得"""
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        encoding_format="float"
    )
    return response.data[0].embedding

def rag_lookup(query):
    # クエリの正規化（小文字化と前後の空白削除）
    normalized_query = query.lower().strip()
    
    # クエリをベクトル化
    query_vector = get_embedding(normalized_query)
    
    # コサイン類似度を計算
    similarities = cosine_similarity([query_vector], vectors)[0]
    
    # 類似度が0.4以上のものを抽出
    relevant_indices = [i for i, sim in enumerate(similarities) if sim >= 0.4]
    
    # 類似度の高い順にソート
    sorted_indices = sorted(relevant_indices, key=lambda i: similarities[i], reverse=True)
    
    # 上位3件の回答を取得
    top_answers = [DF.iloc[i].answer for i in sorted_indices[:3]]
    
    return top_answers

def ask(date_iso: str, time_str: str, tz_name: str) -> str:
    chart = get_chart(date_iso, time_str, tz_name)
    messages = [
        {
            "role": "system",
            "content": open("prompts/system.md", encoding="utf-8").read()
        },
        {
            "role": "user",
            "content": (
                f"生年月日: {date_iso} {time_str} ({tz_name})\n"
                f"チャート: {json.dumps(chart, ensure_ascii=False)}"
            )
        },
    ]

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.7,
        max_tokens=800
    )
    return response.choices[0].message.content.strip()

# ── コマンドラインで使えるように ─────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 占い機能
        try:
            d, t, z = sys.argv[1:4]
        except ValueError:
            print("使い方: python chat.py YYYY-MM-DD HH:MM Asia/Tokyo")
            sys.exit(1)
        print(ask(d, t, z))
    else:
        # FAQ検索機能
        q = input("質問 > ")
        ans = rag_lookup(q)
        if ans:
            print("🧠 FAQ より:\n", "\n".join(ans))
        else:
            print("↪ GPT で生成中…")
            print(ask("2024-03-20", "12:00", "Asia/Tokyo"))  # デフォルトの日時を使用
