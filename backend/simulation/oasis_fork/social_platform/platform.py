"""Platform — action dispatch hub for OASIS commodity fork.

Key pattern: getattr(self, action_type.value)(agent_id, args)
Each ActionType enum maps to an async method by name.

CRITICAL: Platform.running() enforces max 3 params per handler
(self, agent_id, one_data_param). Use tuples to pack multiple values.
"""

import asyncio
import json
import logging
import sqlite3
from datetime import datetime
from typing import Any

from .channel import ActionMessage, Channel
from .database import create_db
from .platform_utils import PlatformUtils
from .typing import ActionType

logger = logging.getLogger(__name__)


class Platform:
    """Central platform that processes agent actions via the Channel."""

    def __init__(
        self,
        db_path: str,
        channel: Channel,
        max_rec_post_len: int = 20,
        refresh_rec_post_count: int = 10,
    ):
        self.db_path = db_path
        self.channel = channel
        self.max_rec_post_len = max_rec_post_len
        self.refresh_rec_post_count = refresh_rec_post_count

        # Initialize database
        self.db, self.db_cursor = create_db(db_path)
        self.pl_utils = PlatformUtils(self.db, self.db_cursor)

        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        """Start processing actions from the channel."""
        self._running = True
        self._task = asyncio.create_task(self._process_loop())

    async def stop(self):
        """Stop processing and close database."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self.db:
            self.db.close()

    async def _process_loop(self):
        """Main loop — read actions from channel and dispatch."""
        while self._running:
            message = None
            try:
                message = await asyncio.wait_for(
                    self.channel.get(), timeout=0.5
                )
                result = await self._dispatch(message)
                if message.result_future and not message.result_future.done():
                    message.result_future.set_result(result)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Platform dispatch error: %s", e)
                if (
                    message is not None
                    and hasattr(message, "result_future")
                    and message.result_future
                    and not message.result_future.done()
                ):
                    message.result_future.set_result(
                        {"success": False, "error": str(e)}
                    )

    async def _dispatch(self, message: ActionMessage) -> dict[str, Any]:
        """Dispatch action to the correct handler method."""
        action = message.action
        handler = getattr(self, action, None)
        if handler is None:
            logger.warning("Unknown action: %s", action)
            return {"success": False, "error": f"Unknown action: {action}"}

        # Dispatch based on action type
        args = message.args
        try:
            if action == ActionType.SIGN_UP.value:
                return await handler(message.agent_id, args.get("user_name", f"agent_{message.agent_id}"))
            elif action == ActionType.DO_NOTHING.value:
                return await handler(message.agent_id)
            elif action == ActionType.CREATE_POST.value:
                return await handler(message.agent_id, args.get("content", ""))
            elif action == ActionType.REFRESH.value:
                return await handler(message.agent_id)
            elif action == ActionType.SUBMIT_TRADE.value:
                trade_tuple = (
                    args.get("commodity", ""),
                    args.get("action", "hold"),
                    args.get("volume_mt", 0),
                    args.get("price_view", 0),
                )
                return await handler(message.agent_id, trade_tuple)
            elif action == ActionType.REROUTE_VESSEL.value:
                reroute_tuple = (
                    args.get("mmsi", 0),
                    args.get("original_port", ""),
                    args.get("new_port", ""),
                    args.get("reason", "disruption"),
                )
                return await handler(message.agent_id, reroute_tuple)
            elif action == ActionType.UPDATE_PRICE_VIEW.value:
                price_tuple = (
                    args.get("commodity", ""),
                    args.get("price_usd", 0),
                    args.get("confidence", 1.0),
                )
                return await handler(message.agent_id, price_tuple)
            elif action == ActionType.IMPOSE_MEASURE.value:
                measure_tuple = (
                    args.get("measure_type", "sanction"),
                    args.get("commodity", ""),
                    args.get("affected_region", ""),
                    args.get("duration_days", 30),
                )
                return await handler(message.agent_id, measure_tuple)
            elif action == ActionType.ACTIVATE_INVENTORY.value:
                inventory_tuple = (
                    args.get("commodity", ""),
                    args.get("volume_mt", 0),
                    args.get("reason", "disruption"),
                )
                return await handler(message.agent_id, inventory_tuple)
            elif action in (
                ActionType.LIKE_POST.value,
                ActionType.DISLIKE_POST.value,
            ):
                return await handler(message.agent_id, args.get("post_id", 0))
            elif action == ActionType.CREATE_COMMENT.value:
                return await handler(
                    message.agent_id,
                    (args.get("post_id", 0), args.get("content", "")),
                )
            elif action == ActionType.FOLLOW.value:
                return await handler(
                    message.agent_id, args.get("followee_id", 0)
                )
            elif action == ActionType.SEARCH_POSTS.value:
                return await handler(
                    message.agent_id, args.get("query", "")
                )
            else:
                # Generic fallback — pass args dict
                return await handler(message.agent_id, args)
        except Exception as e:
            logger.error("Error dispatching %s for agent %d: %s", action, message.agent_id, e)
            return {"success": False, "error": str(e)}

    # ── Core OASIS handlers ────────────────────────────────────

    async def sign_up(self, agent_id: int, user_name: str = "") -> dict[str, Any]:
        """Register agent in the simulation database."""
        user_name = user_name or f"agent_{agent_id}"
        current_time = datetime.now()
        try:
            self.db_cursor.execute(
                "INSERT INTO user (user_id, user_name, created_at) VALUES (?,?,?)",
                (agent_id, user_name, current_time),
            )
            self.db.commit()
            return {"success": True, "user_id": agent_id}
        except sqlite3.IntegrityError:
            return {"success": True, "user_id": agent_id, "note": "already exists"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_post(self, agent_id: int, content: str) -> dict[str, Any]:
        """Create a post (market event / intelligence)."""
        current_time = datetime.now()
        try:
            self.db_cursor.execute(
                "INSERT INTO post (user_id, content, created_at) VALUES (?,?,?)",
                (agent_id, content, current_time),
            )
            self.db.commit()
            self.pl_utils._record_trace(
                agent_id, ActionType.CREATE_POST.value,
                {"content": content[:200]}, current_time,
            )
            return {"success": True, "post_id": self.db_cursor.lastrowid}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def refresh(self, agent_id: int) -> dict[str, Any]:
        """Get recommended posts / market events for agent."""
        posts = self.pl_utils.get_recommended_posts(
            agent_id, limit=self.refresh_rec_post_count
        )
        return {"success": True, "posts": posts}

    async def do_nothing(self, agent_id: int) -> dict[str, Any]:
        """Agent chooses to take no action this step."""
        self.pl_utils._record_trace(
            agent_id, ActionType.DO_NOTHING.value, {}, datetime.now()
        )
        return {"success": True}

    async def like_post(self, agent_id: int, post_id: int) -> dict[str, Any]:
        """Like a post."""
        try:
            self.db_cursor.execute(
                "INSERT OR IGNORE INTO like_post (user_id, post_id) VALUES (?,?)",
                (agent_id, post_id),
            )
            self.db_cursor.execute(
                "UPDATE post SET num_likes = num_likes + 1 WHERE post_id = ?",
                (post_id,),
            )
            self.db.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def dislike_post(self, agent_id: int, post_id: int) -> dict[str, Any]:
        """Dislike a post."""
        try:
            self.db_cursor.execute(
                "INSERT OR IGNORE INTO dislike_post (user_id, post_id) VALUES (?,?)",
                (agent_id, post_id),
            )
            self.db.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def follow(self, agent_id: int, followee_id: int) -> dict[str, Any]:
        """Follow another agent."""
        try:
            self.db_cursor.execute(
                "INSERT OR IGNORE INTO follow (follower_id, followee_id, created_at) VALUES (?,?,?)",
                (agent_id, followee_id, datetime.now()),
            )
            self.db.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def search_posts(self, agent_id: int, query: str) -> dict[str, Any]:
        """Search posts by content."""
        try:
            self.db_cursor.execute(
                "SELECT post_id, user_id, content, created_at FROM post WHERE content LIKE ? ORDER BY created_at DESC LIMIT 20",
                (f"%{query}%",),
            )
            rows = self.db_cursor.fetchall()
            return {
                "success": True,
                "posts": [
                    {"post_id": r[0], "user_id": r[1], "content": r[2], "created_at": r[3]}
                    for r in rows
                ],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_comment(self, agent_id: int, comment_data: tuple) -> dict[str, Any]:
        """Create a comment on a post."""
        post_id, content = comment_data
        try:
            self.db_cursor.execute(
                "INSERT INTO comment (post_id, user_id, content, created_at) VALUES (?,?,?,?)",
                (post_id, agent_id, content, datetime.now()),
            )
            self.db.commit()
            return {"success": True, "comment_id": self.db_cursor.lastrowid}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Commodity handlers (SupplyShock fork) ─────────────────

    async def submit_trade(self, agent_id: int, trade_message: tuple) -> dict[str, Any]:
        """Record a commodity trade decision by an agent.

        trade_message tuple: (commodity, action, volume_mt, price_view)
        - commodity: str — 'coal', 'crude_oil', 'lng', 'iron_ore', etc.
        - action: str — 'buy_spot', 'buy_futures', 'sell', 'hold'
        - volume_mt: float — volume in metric tonnes
        - price_view: float — agent's estimated fair price USD/unit
        """
        commodity, action, volume_mt, price_view = trade_message
        current_time = datetime.now()
        try:
            self.db_cursor.execute(
                "INSERT INTO trade (agent_id, commodity, action, "
                "volume_mt, price_view, created_at) VALUES (?,?,?,?,?,?)",
                (agent_id, commodity, action, volume_mt, price_view, current_time),
            )
            self.db.commit()
            self.pl_utils._record_trace(
                agent_id, ActionType.SUBMIT_TRADE.value,
                {"commodity": commodity, "action": action,
                 "volume_mt": volume_mt, "price_view": price_view},
                current_time,
            )
            return {"success": True, "trade_id": self.db_cursor.lastrowid}
        except Exception as e:
            logger.error("submit_trade error agent %d: %s", agent_id, e)
            return {"success": False, "error": str(e)}

    async def reroute_vessel(self, agent_id: int, reroute_message: tuple) -> dict[str, Any]:
        """Shipper diverts vessel to alternative port due to disruption.

        reroute_message tuple: (mmsi, original_port, new_port, reason)
        - mmsi: int — vessel MMSI identifier
        - original_port: str — original destination port slug
        - new_port: str — new destination port slug
        - reason: str — 'disruption', 'sanction', 'congestion', 'weather'
        """
        mmsi, original_port, new_port, reason = reroute_message
        current_time = datetime.now()
        try:
            self.db_cursor.execute(
                "INSERT INTO vessel_decision (agent_id, mmsi, original_port, "
                "new_port, reason, created_at) VALUES (?,?,?,?,?,?)",
                (agent_id, mmsi, original_port, new_port, reason, current_time),
            )
            self.db.commit()
            self.pl_utils._record_trace(
                agent_id, ActionType.REROUTE_VESSEL.value,
                {"mmsi": mmsi, "from": original_port, "to": new_port,
                 "reason": reason},
                current_time,
            )
            return {"success": True, "new_port": new_port}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def update_price_view(self, agent_id: int, price_message: tuple) -> dict[str, Any]:
        """Trader records updated price estimate for commodity.

        price_message tuple: (commodity, price_usd, confidence)
        - commodity: str
        - price_usd: float — estimated fair price
        - confidence: float — 0.0 to 1.0
        """
        commodity, price_usd, confidence = price_message
        current_time = datetime.now()
        try:
            self.db_cursor.execute(
                "INSERT INTO market_state (commodity, agent_id, price_view, "
                "confidence, created_at) VALUES (?,?,?,?,?)",
                (commodity, agent_id, price_usd, confidence, current_time),
            )
            self.db.commit()
            self.pl_utils._record_trace(
                agent_id, ActionType.UPDATE_PRICE_VIEW.value,
                {"commodity": commodity, "price_view": price_usd,
                 "confidence": confidence},
                current_time,
            )
            return {"success": True, "recorded_price": price_usd}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def impose_measure(self, agent_id: int, measure_message: tuple) -> dict[str, Any]:
        """Government agent imposes trade measure on commodity flow.

        measure_message tuple: (measure_type, commodity, affected_region, duration_days)
        - measure_type: str — 'sanction', 'export_ban', 'tariff', 'quota'
        - commodity: str
        - affected_region: str — country code e.g. 'RU', 'AU'
        - duration_days: int
        """
        measure_type, commodity, affected_region, duration_days = measure_message
        current_time = datetime.now()
        self.pl_utils._record_trace(
            agent_id, ActionType.IMPOSE_MEASURE.value,
            {"type": measure_type, "commodity": commodity,
             "region": affected_region, "duration_days": duration_days},
            current_time,
        )
        return {"success": True, "measure": measure_type}

    async def activate_inventory(self, agent_id: int, inventory_message: tuple) -> dict[str, Any]:
        """Buyer activates strategic inventory / emergency stock.

        inventory_message tuple: (commodity, volume_mt, reason)
        - commodity: str
        - volume_mt: float — volume released from strategic reserves
        - reason: str — 'disruption', 'price_spike', 'precaution'
        """
        commodity, volume_mt, reason = inventory_message
        current_time = datetime.now()
        self.pl_utils._record_trace(
            agent_id, ActionType.ACTIVATE_INVENTORY.value,
            {"commodity": commodity, "volume_mt": volume_mt, "reason": reason},
            current_time,
        )
        return {"success": True, "released_mt": volume_mt}
