"""
Planning constants.

This module defines deterministic execution ordering for
provider-independent actions produced by the Planning Engine.
"""

from app.domain.enums import ActionType


ACTION_ORDER: dict[ActionType, int] = {
    # Order: Categorise, flag, and escalate first, then ignore, archive, and move.
    ActionType.ADD_CATEGORY: 10,
    ActionType.FLAG_FOR_REVIEW: 20,
    ActionType.ESCALATE: 30,
    ActionType.IGNORE: 40,
    ActionType.ARCHIVE: 50,
    ActionType.MOVE_TO_FOLDER: 60,
}