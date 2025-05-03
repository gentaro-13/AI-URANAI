import os
import json
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

# .envファイルから環境変数を読み込む
load_dotenv()

# OpenAI APIの設定
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def get_embedding(text):
    """OpenAI Embeddings APIを使用してテキストのベクトルを取得"""
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        encoding_format="float"
    )
    return response.data[0].embedding

def main():
    # FAQデータの読み込み
    df = pd.read_csv('faq.csv')
    
    # 質問と回答を結合してベクトル化
    texts = (df['question'] + " " + df['answer']).tolist()
    
    # 各テキストをベクトル化
    vectors = []
    for text in texts:
        vector = get_embedding(text)
        vectors.append(vector)
    
    # ベクトルをnumpy配列に変換
    vectors = np.array(vectors)
    
    # ベクトルを保存
    np.save('faq_vectors.npy', vectors)
    
    # FAQデータをpickle形式で保存
    df.to_pickle('faq.pkl')
    
    print("ベクトル化が完了しました。")

if __name__ == "__main__":
    main() 