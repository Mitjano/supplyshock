"""Action types and platform types for OASIS commodity fork.

ActionType enum values map 1:1 to async method names on Platform class.
Platform.running() dispatches via getattr(self, action.value).
"""

from enum import Enum


class ActionType(str, Enum):
    """All possible agent actions in the simulation."""

    # ── Original OASIS actions ────────────────────────────────────
    SIGN_UP = "sign_up"
    CREATE_POST = "create_post"
    LIKE_POST = "like_post"
    UNLIKE_POST = "unlike_post"
    DISLIKE_POST = "dislike_post"
    UNDO_DISLIKE_POST = "undo_dislike_post"
    SEARCH_POSTS = "search_posts"
    SEARCH_USER = "search_user"
    FOLLOW = "follow"
    UNFOLLOW = "unfollow"
    MUTE = "mute"
    UNMUTE = "unmute"
    TREND = "trend"
    CREATE_COMMENT = "create_comment"
    LIKE_COMMENT = "like_comment"
    UNLIKE_COMMENT = "unlike_comment"
    DISLIKE_COMMENT = "dislike_comment"
    UNDO_DISLIKE_COMMENT = "undo_dislike_comment"
    DO_NOTHING = "do_nothing"
    REFRESH = "refresh"
    PURCHASE_PRODUCT = "purchase_product"
    CREATE_PRODUCT = "create_product"
    SEND_MESSAGE = "send_message"
    RECEIVE_MESSAGE = "receive_message"

    # ── Commodity actions (SupplyShock fork) ─────────────────────
    SUBMIT_TRADE = "submit_trade"
    REROUTE_VESSEL = "reroute_vessel"
    UPDATE_PRICE_VIEW = "update_price_view"
    IMPOSE_MEASURE = "impose_measure"
    ACTIVATE_INVENTORY = "activate_inventory"


class DefaultPlatformType(str, Enum):
    """Platform types supported by OasisEnv."""

    TWITTER = "twitter"
    REDDIT = "reddit"
    COMMODITY = "commodity"
