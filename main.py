
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

# Yerel Ollama modeline bağlan
llm = ChatOllama(
    model="qwen3:8b",
    temperature=0
)

# Prompt şablonu
prompt = ChatPromptTemplate.from_messages([
    ("system", "Sen uzman bir SQL ve veri analizi asistanısın."),
    ("human", "{question}")
])

# LangChain Expression Language (LCEL)
chain = prompt | llm

response = chain.invoke({
    "question": "SQL'de ROW_NUMBER ile DENSE_RANK arasındaki fark nedir?"
})

print(response.content)
