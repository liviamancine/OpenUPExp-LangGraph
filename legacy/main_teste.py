from typing import TypedDict

from langgraph.graph import StateGraph, START, END


class OpenUPExpState(TypedDict, total=False):
    resultado_worker1: str
    resultado_worker2: str
    resultado_worker3: str


def worker_1(state: OpenUPExpState):
    print("Worker 1 recebeu:", state)

    return {
        "resultado_worker1": "Resultado produzido pelo Worker 1"
    }


def worker_2(state: OpenUPExpState):
    print("Worker 2 recebeu:", state)

    return {
        "resultado_worker2": "Resultado produzido pelo Worker 2"
    }


async def worker_3(state: OpenUPExpState):
    print("Worker 3 executando...")

    resultado_worker1 = (
        state["blackboard"]
        ["visao_explicabilidade"]
        ["escopo"]
        ["escopo"]
    )

    resultado_worker2 = (
        state["blackboard"]
        ["visao_explicabilidade"]
        ["posicionamento"]
        ["posicionamentos"]
    )

    print("\nWorker 3 consultou o Blackboard:")
    print("Worker 1:", resultado_worker1)
    print("Worker 2:", resultado_worker2)

    resultado = await b.DescribeStakeholders(
        resultado_worker1=resultado_worker1,
        resultado_worker2=resultado_worker2
    )

    resultado_serializado = resultado.model_dump()

    state["blackboard"]["visao_explicabilidade"][
        "stakeholders"
    ] = resultado_serializado

    return state


builder = StateGraph(OpenUPExpState)

builder.add_node("worker_1", worker_1)
builder.add_node("worker_2", worker_2)
builder.add_node("worker_3", worker_3)

builder.add_edge(START, "worker_1")
builder.add_edge("worker_1", "worker_2")
builder.add_edge("worker_2", "worker_3")
builder.add_edge("worker_3", END)

graph = builder.compile()

resultado = graph.invoke({})

print("\nEstado final:")
print(resultado)