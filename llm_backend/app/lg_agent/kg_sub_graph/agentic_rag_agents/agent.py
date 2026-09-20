"""LangGraph Studio 调试入口，不参与后端服务运行。

注意：本模块在 **导入时** 就会连接 Neo4j 并调用 OpenAI，仅供
`langgraph dev`（LangGraph Studio）加载，请不要从业务代码 import 它。
后端服务的真实链路是 app/lg_agent/lg_builder.py。
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from neo4j import GraphDatabase

from app.lg_agent.kg_sub_graph.agentic_rag_agents.retrievers.cypher_examples import (
    Neo4jVectorSearchCypherExampleRetriever,
)

# 与后端服务共用 llm_backend/.env，保证单独跑 Studio 时也能拿到模型与库配置
load_dotenv(Path(__file__).resolve().parents[4] / ".env")

# 命名桥接：项目 .env 里的连接串变量叫 NEO4J_URL（见 app/core/config.py），
# 而 langchain_neo4j 的 Neo4jGraph 与 neo4j 驱动默认只认 NEO4J_URI。
# 不做这一步，套用项目 .env 时这里会取到空 URI，表现为连接失败。
if not os.getenv("NEO4J_URI") and os.getenv("NEO4J_URL"):
    os.environ["NEO4J_URI"] = os.environ["NEO4J_URL"]

# from app.lg_agent.kg_sub_graph.agentic_rag_agents.workflows.single_agent import create_text2cypher_agent
# 直接从子模块导入：workflows.multi_agent 的 __init__ 只导出主链路需要的
# create_multi_tool_workflow，避免把可视化工作流的依赖拉进服务启动路径。
from app.lg_agent.kg_sub_graph.agentic_rag_agents.workflows.multi_agent.text2cypher_with_visualization import (
    create_text2cypher_with_visualization_workflow,
)

neo4j_graph = Neo4jGraph(enhanced_schema=True)
llm = ChatOpenAI()
embedder = OpenAIEmbeddings(model="text-embedding-ada-002")

neo4j_driver = GraphDatabase.driver(
    uri=os.getenv("NEO4J_URI", ""),
    auth=(os.getenv("NEO4J_USERNAME", ""), os.getenv("NEO4J_PASSWORD", "")),
)
vector_index_name = "cypher_query_vector_index"

cypher_example_retriever = Neo4jVectorSearchCypherExampleRetriever(
    neo4j_driver=neo4j_driver, vector_index_name=vector_index_name, embedder=embedder
)

# Create the graph to be found by LangGraph Studio
graph = create_text2cypher_with_visualization_workflow(
    llm=llm,
    cypher_example_retriever=cypher_example_retriever,
    llm_cypher_validation=False,
    graph=neo4j_graph,
)
