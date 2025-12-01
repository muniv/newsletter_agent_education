"""CrewAI newsletter production workflow with MCP tools integration."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Any

from crewai import Agent, Crew, Process, Task
from crewai.tools import BaseTool
from dotenv import load_dotenv
from fastmcp import Client, FastMCP
from pydantic import BaseModel, Field

from newsletter_server import app as mcp_app

load_dotenv()

PROXY_SERVER = FastMCP.as_proxy(mcp_app)


def _call_mcp(tool_name: str, **arguments: Any) -> str:
    """MCP 도구를 비동기적으로 호출합니다."""
    async def _invoke() -> str:
        async with Client(PROXY_SERVER) as client:
            result = await client.call_tool(tool_name, arguments)
            if result.structured_content:
                return json.dumps(result.structured_content, ensure_ascii=False, indent=2)
            if result.content:
                texts = []
                for block in result.content:
                    text = getattr(block, "text", None)
                    if text:
                        texts.append(text)
                if texts:
                    return "\n".join(texts)
            return "(no content returned)"

    return asyncio.run(_invoke())


class FetchNewsInput(BaseModel):
    count: str = Field(default="5", description="수집할 뉴스 개수")

class FetchNewsTool(BaseTool):
    name: str = "fetch_news_tool"
    description: str = "AI/Tech 뉴스를 수집합니다"
    args_schema: type[BaseModel] = FetchNewsInput

    def _run(self, count: str = "5") -> str:
        try:
            return _call_mcp("fetch_tech_news", count=int(count))
        except Exception as e:
            return f"뉴스 수집 중 오류: {str(e)}"


class CreateNewsletterInput(BaseModel):
    title: str = Field(description="뉴스레터 제목")
    content: str = Field(description="뉴스 내용")
    intro: str = Field(default="", description="서론 텍스트")

class CreateNewsletterTool(BaseTool):
    name: str = "create_newsletter_tool"
    description: str = "HTML 뉴스레터를 생성합니다"
    args_schema: type[BaseModel] = CreateNewsletterInput

    def _run(self, title: str, content: str, intro: str = "") -> str:
        return _call_mcp("create_newsletter_html", title=title, news_content=content, intro_text=intro)




class SendEmailInput(BaseModel):
    recipient: str = Field(description="받는 사람 이메일")
    subject: str = Field(description="이메일 제목")
    body: str = Field(description="이메일 본문")

class SendEmailTool(BaseTool):
    name: str = "send_email_tool"
    description: str = "이메일을 발송합니다"
    args_schema: type[BaseModel] = SendEmailInput

    def _run(self, recipient: str, subject: str, body: str) -> str:
        return _call_mcp("send_email", to=recipient, subject=subject, body=body)




def build_agents(model_name: str) -> tuple[Agent, Agent, Agent]:
    """뉴스레터 제작을 위한 3개의 에이전트를 생성합니다."""

    news_researcher = Agent(
        role="News Researcher",
        goal="AI와 기술 분야의 최신 뉴스를 수집하고 중요도에 따라 필터링한다.",
        backstory=(
            "5년 차 테크 저널리스트로, AI와 스타트업 생태계 동향을 추적하는 전문가. "
            "독자들이 정말 알아야 할 뉴스와 트렌드를 선별하는 눈이 뛰어나다."
        ),
        llm=model_name,
        verbose=True,
    )

    content_editor = Agent(
        role="Content Editor",
        goal="수집된 뉴스를 독자 친화적으로 큐레이션하고 한국어로 HTML 뉴스레터를 완성한다.",
        backstory=(
            "B2B 테크 미디어에서 7년간 콘텐츠를 편집한 베테랑. "
            "복잡한 기술 내용을 일반인도 이해할 수 있게 한국어로 정리하고 뉴스레터로 디자인하는 능력이 탁월하다."
        ),
        llm=model_name,
        verbose=True,
    )

    email_sender = Agent(
        role="Email Campaign Manager",
        goal="완성된 뉴스레터를 구독자들에게 효과적으로 발송한다.",
        backstory=(
            "이메일 마케팅 플랫폼에서 4년간 캠페인을 관리한 전문가. "
            "발송 타이밍, 제목 최적화를 통해 성과를 극대화한다."
        ),
        llm=model_name,
        verbose=True,
    )

    return news_researcher, content_editor, email_sender


def build_tasks(
    news_researcher: Agent,
    content_editor: Agent,
    email_sender: Agent,
    recipient_email: str
) -> tuple[Task, Task, Task]:
    """뉴스레터 제작 워크플로우의 3개 태스크를 생성합니다."""

    fetch_news = Task(
        name="뉴스 수집",
        description=(
            "최신 AI와 기술 뉴스를 수집하세요. "
            "fetch_news_tool을 사용하여 5개의 최신 뉴스를 가져오고, "
            "각 뉴스의 중요도와 관련성을 평가하여 상위 3개를 선별하세요."
        ),
        expected_output="선별된 3개 뉴스의 제목, 링크, 요약 정보",
        agent=news_researcher,
        tools=[FetchNewsTool()],
    )

    # 한국 시간대(KST) 기준 오늘 날짜 계산
    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst)
    today_str = today.strftime("%Y년 %m월 %d일")
    
    create_newsletter = Task(
        name="뉴스레터 제작",
        description=(
            f"수집된 뉴스를 분석하고 독자 친화적으로 큐레이션한 후, "
            f"create_newsletter_tool을 사용하여 HTML 뉴스레터를 완성하세요. "
            f"제목은 반드시 'AI 뉴스레터 - {today_str}' 형식으로 사용하고, "
            f"서론(intro_text)과 뉴스 내용은 모두 한국어로 작성하세요. "
            f"각 뉴스에 대한 인사이트와 매력적인 서론을 한국어로 포함하세요."
        ),
        expected_output="완성된 HTML 뉴스레터 (한국어로 작성됨)",
        agent=content_editor,
        context=[fetch_news],
        tools=[CreateNewsletterTool()],
    )

    send_newsletter = Task(
        name="뉴스레터 발송",
        description=(
            f"완성된 HTML 뉴스레터를 {recipient_email}에게 발송하세요. "
            "HTML 뉴스레터를 이메일 본문으로 사용하고, "
            "적절한 제목을 만들어서 send_email_tool을 사용하여 실제 발송하세요."
        ),
        expected_output="이메일 발송 완료 확인 메시지",
        agent=email_sender,
        context=[create_newsletter],
        tools=[SendEmailTool()],
    )

    return fetch_news, create_newsletter, send_newsletter


def run_newsletter_crew(recipient_email: str, model_name: str) -> str:
    """뉴스레터 제작 및 발송을 실행합니다."""
    news_researcher, content_editor, email_sender = build_agents(model_name)
    fetch_news, create_newsletter, send_newsletter = build_tasks(
        news_researcher, content_editor, email_sender, recipient_email
    )

    crew = Crew(
        agents=[news_researcher, content_editor, email_sender],
        tasks=[fetch_news, create_newsletter, send_newsletter],
        process=Process.sequential,
        verbose=True,
    )

    result = crew.kickoff()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="AI 뉴스레터 자동 제작 및 발송 시스템")
    parser.add_argument(
        "--email",
        default=os.getenv("RECIPIENT_EMAIL") or os.getenv("EMAIL") or os.getenv("GMAIL_USER"),
        help="뉴스레터를 받을 이메일 주소 (환경 변수 RECIPIENT_EMAIL, EMAIL, 또는 GMAIL_USER에서도 읽을 수 있음)"
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        help="사용할 LLM 이름(OpenAI 호환)",
    )
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY 환경 변수를 설정해 주세요.")
    
    if not args.email:
        raise RuntimeError("이메일 주소를 --email 인자로 제공하거나 RECIPIENT_EMAIL 또는 EMAIL 환경 변수로 설정해 주세요.")

    print(f"🗞️  AI 뉴스레터 제작을 시작합니다 (수신자: {args.email})")
    print("=" * 60)

    result = run_newsletter_crew(args.email, args.model)

    print("\n" + "=" * 60)
    print("✅ 뉴스레터 제작 및 발송 완료!")
    print("📧 결과:", result)


if __name__ == "__main__":
    main()