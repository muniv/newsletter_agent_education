"""Newsletter MCP server with email composition/sending and news fetching tools."""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict
import xml.etree.ElementTree as ET

import requests
from dotenv import load_dotenv
from fastmcp import FastMCP
from openai import OpenAI

load_dotenv()

app = FastMCP(
    name="newsletter-mcp-server",
    instructions="Newsletter creation tools with email composition, sending, and news fetching.",
)



@app.tool
def send_email(to: str, subject: str, body: str) -> str:
    """Gmail SMTP를 통해 이메일을 발송합니다.

    Args:
        to: 받는 사람 이메일 주소
        subject: 제목
        body: 본문
    """
    gmail_user = os.getenv("GMAIL_USER")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")

    if not gmail_user or not gmail_password:
        return "❌ Gmail 설정이 누락되었습니다. GMAIL_USER와 GMAIL_APP_PASSWORD를 확인해주세요."

    try:
        msg = MIMEMultipart()
        msg['From'] = gmail_user
        msg['To'] = to
        msg['Subject'] = subject

        # HTML 콘텐츠인지 확인하여 적절한 MIME 타입 설정
        if body.strip().startswith('<!DOCTYPE html>') or '<html>' in body.lower():
            msg.attach(MIMEText(body, 'html', 'utf-8'))
        else:
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(gmail_user, gmail_password)
            server.send_message(msg)

        return f"✅ 이메일이 성공적으로 발송되었습니다: {to}"

    except Exception as e:
        return f"❌ 이메일 발송 실패: {str(e)}"


@app.tool
def fetch_tech_news(count: int = 5) -> str:
    """AI/Tech 관련 최신 뉴스를 RSS 피드에서 가져옵니다.

    Args:
        count: 가져올 뉴스 개수 (기본값: 5)
    """
    try:
        # TechCrunch AI RSS 피드 사용
        response = requests.get("https://techcrunch.com/category/artificial-intelligence/feed/", timeout=10)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        items = root.findall('.//item')[:count]

        news_list = []
        for item in items:
            title = item.find('title').text if item.find('title') is not None else "제목 없음"
            link = item.find('link').text if item.find('link') is not None else ""
            description = item.find('description').text if item.find('description') is not None else ""

            # HTML 태그 제거
            import re
            clean_desc = re.sub(r'<[^>]+>', '', description)[:200] + "..."

            news_list.append(f"📰 {title}\n🔗 {link}\n📝 {clean_desc}\n")

        return "\n".join(news_list)

    except Exception as e:
        # RSS 실패 시 샘플 뉴스 반환
        return f"""📰 OpenAI GPT-4 Turbo 새 업데이트 발표
🔗 https://example.com/gpt4-update
📝 OpenAI가 GPT-4 Turbo의 새로운 기능을 발표했습니다...

📰 Google Bard AI 한국어 지원 확대
🔗 https://example.com/bard-korean
📝 구글이 Bard AI의 한국어 지원을 대폭 확대한다고 발표...

📰 AI 스타트업 투자 급증, 2024년 전망
🔗 https://example.com/ai-investment
📝 올해 AI 스타트업에 대한 투자가 전년 대비 150% 증가...

(실제 RSS 피드 연결 실패로 샘플 데이터 표시: {str(e)})"""


@app.tool
def create_newsletter_html(title: str, news_content: str, intro_text: str = "") -> str:
    """뉴스 내용을 기반으로 HTML 뉴스레터를 생성합니다.

    Args:
        title: 뉴스레터 제목
        news_content: 뉴스 내용
        intro_text: 서론 텍스트 (선택사항)
    """
    html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
        .header {{ background-color: #2c3e50; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; }}
        .news-item {{ margin-bottom: 30px; border-bottom: 1px solid #eee; padding-bottom: 20px; }}
        .footer {{ background-color: #ecf0f1; padding: 15px; text-align: center; color: #7f8c8d; }}
        a {{ color: #3498db; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{title}</h1>
    </div>

    <div class="content">
        {f'<p>{intro_text}</p>' if intro_text else ''}

        <div class="news-section">
            <pre style="white-space: pre-wrap; font-family: Arial, sans-serif;">{news_content}</pre>
        </div>
    </div>

    <div class="footer">
        <p>이 뉴스레터는 AI 멀티 에이전트 시스템으로 자동 생성되었습니다.</p>
        <p>문의사항이 있으시면 연락주세요.</p>
    </div>
</body>
</html>
"""
    return html_template




if __name__ == "__main__":
    print("🚀 Newsletter MCP Server 시작")
    print("📧 사용 가능한 도구:")
    print("  - send_email: Gmail SMTP로 발송")
    print("  - fetch_tech_news: AI/Tech 뉴스 수집")
    print("  - create_newsletter_html: HTML 뉴스레터 생성")
    print()
    print("🌐 HTTP Transport 사용 - http://localhost:8000/mcp/")
    print("⚠️  환경변수 확인: OPENAI_API_KEY, GMAIL_USER, GMAIL_APP_PASSWORD")
    print()

    app.run(transport="http", host="127.0.0.1", port=8000)