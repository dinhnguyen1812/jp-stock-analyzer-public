import os
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")

def analyze_news_with_gpt(news_items):
    if not news_items:
        return "No news available to analyze.", "neutral"

    headlines = "\n".join([f"- {item['headline']}" for item in news_items])
    prompt = f"""
以下は企業の最近のニュース見出しです。

{headlines}

これらのニュースを要約し、投資家の感情（ポジティブ・ネガティブ・ニュートラル）を1語で評価してください。

出力形式：
Summary: （要約）
Sentiment: positive / neutral / negative
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        content = response.choices[0].message["content"]

        # Split summary and sentiment
        summary = ""
        sentiment = "neutral"
        for line in content.splitlines():
            if line.lower().startswith("summary:"):
                summary = line.split(":", 1)[1].strip()
            elif line.lower().startswith("sentiment:"):
                sentiment = line.split(":", 1)[1].strip().lower()

        return summary, sentiment
    except Exception as e:
        print("GPT error:", e)
        return "Analysis failed.", "neutral"

