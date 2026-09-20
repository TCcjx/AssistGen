"""上游示例脚本：BBC Recipes 多工具智能体演示（本项目未使用）。

注意：本文件依赖上游仓库的目录布局（顶层包 `ps_genai_agents`、`data.bbc_recipes`
以及可选包 `langchain_openai`），这些在本项目中均不存在，直接运行会 ImportError。
项目实际的图谱智能体入口为 `app/lg_agent/lg_builder.py`，无需本文件参与。
保留原因：便于对照上游实现。
"""

from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph
from langchain_openai import ChatOpenAI

from data.bbc_recipes.queries import get_cypher_statements_dictionary, get_tool_schemas
from ps_genai_agents.components.text2cypher import get_text2cypher_schema
from ps_genai_agents.retrievers.cypher_examples import YAMLCypherExampleRetriever
from ps_genai_agents.workflows.multi_agent import create_multi_tool_workflow

load_dotenv()

neo4j_graph = Neo4jGraph(enhanced_schema=True)

llm = ChatOpenAI(model="gpt-4o", temperature=0)


cypher_query_yaml_file_path = "data/bbc_recipes/queries/queries.yml"

cypher_queries_for_tools = (
    get_cypher_statements_dictionary()
)  # this is used to find Cypher queries based on a name

tool_schemas = (
    get_tool_schemas() + [get_text2cypher_schema()]
)  # these are Pydantic classes that define the available Cypher queries and their parameters

cypher_example_retriever = YAMLCypherExampleRetriever(
    cypher_query_yaml_file_path=cypher_query_yaml_file_path
)

scope_description = "This application may answer questions related to cooking recipes and their authors."


graph = create_multi_tool_workflow(
    llm=llm,
    graph=neo4j_graph,
    tool_schemas=tool_schemas,
    predefined_cypher_dict=cypher_queries_for_tools,
    scope_description=scope_description,
    cypher_example_retriever=cypher_example_retriever,
    llm_cypher_validation=False,
    attempt_cypher_execution_on_final_attempt=True,
    default_to_text2cypher=False,
)
