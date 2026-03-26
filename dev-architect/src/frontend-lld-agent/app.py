import logging
from graph import build_graph
from state import ARCHITECTURE_DOC
from utils import print_lld

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s – %(message)s",
)

if __name__ == "__main__":
    print("\nFrontend LLD Agent")
    print("─" * 40)

    graph = build_graph()
    result = graph.invoke({
        "architecture_doc": ARCHITECTURE_DOC,
        "final_lld": "",
    })

    print_lld(result["final_lld"])