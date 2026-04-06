import logging

from graph import build_agent
from state import SAMPLE_USER_INPUT, SAMPLE_REQUIREMENT_DOC, SAMPLE_ARCHITECTURE_DOC

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    logger.info("Starting Frontend LLD Agent ...")

    agent = build_agent()
    logger.info("Agent built successfully.")

    logger.info("Running Frontend LLD Agent with sample inputs ...")
    response = agent.run(
        user_input=SAMPLE_USER_INPUT,
        requirement_doc=SAMPLE_REQUIREMENT_DOC,
        architecture_doc=SAMPLE_ARCHITECTURE_DOC,
    )

    logger.info("Frontend LLD Agent completed successfully.")
    logger.info("Output:\n%s", response.output)

    if response.is_validated:
        logger.info("Validation score  : %.2f", response.validation_score)
        logger.info("Was refined       : %s", response.was_refined)
        if response.was_refined:
            logger.info("Refinement runs   : %d", response.refinement_attempts)