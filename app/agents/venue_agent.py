
from datetime import datetime
from decimal import Decimal

from app.database import get_db_connection
from app.agents.base_agent import BaseAgent
from app.agents.message import ACLMessage, Performative


class VenueAgent(BaseAgent):
    """
    Handles venue availability and private venue hire requests.
    All replies are sent through the ACL MessageBus.
    """

    TURNAROUND_MINUTES = 60

    def receive_message(self, message: ACLMessage):
        if message.performative != Performative.REQUEST:
            return self._reply(
                message,
                Performative.REFUSE,
                {"reason": "VenueAgent only accepts REQUEST messages."}
            )

        action = message.content.get("action")

        if action == "CHECK_AVAILABILITY":
            return self.check_availability(message)

        if action == "REQUEST_PRIVATE_HIRE":
            return self.request_private_hire(message)

        return self._reply(
            message,
            Performative.REFUSE,
            {"reason": f"Unsupported action: {action}"}
        )

    # -------------------------------------------------
    # DATETIME VALIDATION
    # -------------------------------------------------

    def _parse_datetime(self, value):
        if not isinstance(value, str):
            raise ValueError("A valid datetime string is required.")

        try:
            result = datetime.fromisoformat(value)
        except ValueError:
            raise ValueError("Invalid datetime format.")

        if result.tzinfo is None:
            raise ValueError("Timezone is required.")

        return result

    def _validate_period(self, content):
        start_time = self._parse_datetime(
            content.get("start_time")
        )

        end_time = self._parse_datetime(
            content.get("end_time")
        )

        if end_time <= start_time:
            raise ValueError("end_time must be after start_time.")

        return start_time, end_time

    # -------------------------------------------------
    # ACL MESSAGE REPLY
    # -------------------------------------------------

    def _reply(self, request, performative, content):
        return self.send_message(
            receiver=request.sender,
            performative=performative,
            content=content,
            conversation_id=request.conversation_id
        )

    # -------------------------------------------------
    # CHECK VENUE CONFLICTS
    # -------------------------------------------------

    def _check_conflict(
        self, cursor, venue_id, start_time, end_time
    ):
        buffer = self.TURNAROUND_MINUTES

        # Check existing events
        cursor.execute(
            """
            SELECT id
            FROM events
            WHERE venue_id = %s
              AND status != 'CANCELLED'
              AND start_time < (
                  %s + (%s * INTERVAL '1 minute')
              )
              AND end_time > (
                  %s - (%s * INTERVAL '1 minute')
              )
            LIMIT 1
            """,
            (
                venue_id,
                end_time,
                buffer,
                start_time,
                buffer
            )
        )

        if cursor.fetchone():
            return (
                "An event is scheduled during this time "
                "or its turnaround period."
            )

        # Check existing private hire requests
        cursor.execute(
            """
            SELECT id
            FROM venue_hire_requests
            WHERE venue_id = %s
              AND status IN ('PENDING', 'CONFIRMED')
              AND start_time < (
                  %s + (%s * INTERVAL '1 minute')
              )
              AND end_time > (
                  %s - (%s * INTERVAL '1 minute')
              )
            LIMIT 1
            """,
            (
                venue_id,
                end_time,
                buffer,
                start_time,
                buffer
            )
        )

        if cursor.fetchone():
            return (
                "Another private hire request "
                "conflicts with this time."
            )

        return None

    # -------------------------------------------------
    # FIND ALTERNATIVE VENUES
    # -------------------------------------------------

    def _find_alternative_venues(
        self,
        cursor,
        requested_venue_id,
        start_time,
        end_time,
        guest_count
    ):
        cursor.execute(
            """
            SELECT id, name, location, capacity, hourly_rate
            FROM venues
            WHERE id != %s
              AND private_hire_available = TRUE
              AND capacity >= %s
            ORDER BY hourly_rate ASC
            """,
            (
                requested_venue_id,
                guest_count
            )
        )

        candidates = cursor.fetchall()
        alternatives = []

        for venue in candidates:

            conflict = self._check_conflict(
                cursor,
                venue["id"],
                start_time,
                end_time
            )

            if conflict is None:

                alternatives.append({
                    "venue_id": venue["id"],
                    "venue_name": venue["name"],
                    "location": venue["location"],
                    "capacity": venue["capacity"],
                    "hourly_rate": str(
                        venue["hourly_rate"]
                    )
                })

            if len(alternatives) >= 3:
                break

        return alternatives

    # -------------------------------------------------
    # CHECK AVAILABILITY
    # -------------------------------------------------

    def check_availability(self, message):

        try:
            content = message.content

            venue_id = int(content["venue_id"])

            start_time, end_time = self._validate_period(
                content
            )

            with get_db_connection() as connection:

                with connection.cursor() as cursor:

                    cursor.execute(
                        """
                        SELECT
                            id,
                            name,
                            location,
                            capacity,
                            hourly_rate,
                            private_hire_available
                        FROM venues
                        WHERE id = %s
                        FOR UPDATE
                        """,
                        (venue_id,)
                    )

                    venue = cursor.fetchone()

                    if not venue:
                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {
                                "reason": "Venue not found."
                            }
                        )

                    conflict = self._check_conflict(
                        cursor,
                        venue_id,
                        start_time,
                        end_time
                    )

                    if conflict:

                        alternatives = (
                            self._find_alternative_venues(
                                cursor,
                                venue_id,
                                start_time,
                                end_time,
                                int(
                                    content.get(
                                        "guest_count", 1
                                    )
                                )
                            )
                        )

                        return self._reply(
                            message,
                            (
                                Performative.PROPOSE
                                if alternatives
                                else Performative.REFUSE
                            ),
                            {
                                "reason": conflict,
                                "requested_venue_id": venue_id,
                                "alternatives": alternatives
                            }
                        )

            # Save agent state
            self.state["last_availability_check"] = {
                "venue_id": venue_id,
                "checked_at": (
                    datetime.now().astimezone().isoformat()
                ),
                "available": True
            }

            self.save_state()

            return self._reply(
                message,
                Performative.AGREE,
                {
                    "venue_id": venue["id"],
                    "venue_name": venue["name"],
                    "available": True,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat()
                }
            )

        except (KeyError, TypeError, ValueError) as error:

            return self._reply(
                message,
                Performative.REFUSE,
                {
                    "reason": str(error)
                }
            )

    # -------------------------------------------------
    # PRIVATE VENUE HIRE REQUEST
    # -------------------------------------------------

    def request_private_hire(self, message):

        try:
            content = message.content

            venue_id = int(content["venue_id"])

            guest_count = int(content["guest_count"])

            purpose = str(
                content["purpose"]
            ).strip()

            user_id = int(content["user_id"])

            start_time, end_time = self._validate_period(
                content
            )

            if guest_count <= 0:
                raise ValueError(
                    "guest_count must be greater than zero."
                )

            if not purpose:
                raise ValueError(
                    "A purpose is required."
                )

            with get_db_connection() as connection:

                with connection.cursor() as cursor:

                    cursor.execute(
                        """
                        SELECT
                            id,
                            name,
                            capacity,
                            hourly_rate,
                            private_hire_available
                        FROM venues
                        WHERE id = %s
                        FOR UPDATE
                        """,
                        (venue_id,)
                    )

                    venue = cursor.fetchone()

                    if not venue:
                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {
                                "reason": "Venue not found."
                            }
                        )

                    # Check private hire availability
                    if not venue["private_hire_available"]:

                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {
                                "reason": (
                                    "Private hire is not available "
                                    "for this venue."
                                )
                            }
                        )

                    # Check venue capacity
                    if guest_count > venue["capacity"]:

                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {
                                "reason": (
                                    "Guest count exceeds venue capacity."
                                ),
                                "venue_capacity": venue["capacity"]
                            }
                        )

                    # Check time conflicts
                    conflict = self._check_conflict(
                        cursor,
                        venue_id,
                        start_time,
                        end_time
                    )

                    if conflict:

                        alternatives = (
                            self._find_alternative_venues(
                                cursor,
                                venue_id,
                                start_time,
                                end_time,
                                guest_count
                            )
                        )

                        return self._reply(
                            message,
                            (
                                Performative.PROPOSE
                                if alternatives
                                else Performative.REFUSE
                            ),
                            {
                                "reason": conflict,
                                "alternatives": alternatives
                            }
                        )

                    # Calculate private hire price
                    duration_hours = (
                        Decimal(
                            str(
                                (
                                    end_time - start_time
                                ).total_seconds()
                            )
                        ) / Decimal("3600")
                    )

                    quoted_price = (
                        Decimal(
                            str(venue["hourly_rate"])
                        ) * duration_hours
                    ).quantize(
                        Decimal("0.01")
                    )

                    # Save private hire request
                    cursor.execute(
                        """
                        INSERT INTO venue_hire_requests (
                            user_id,
                            venue_id,
                            start_time,
                            end_time,
                            purpose,
                            guest_count,
                            quoted_price,
                            status
                        )
                        VALUES (
                            %s, %s, %s, %s, %s, %s, %s,
                            'CONFIRMED'
                        )
                        RETURNING id
                        """,
                        (
                            user_id,
                            venue_id,
                            start_time,
                            end_time,
                            purpose,
                            guest_count,
                            quoted_price
                        )
                    )

                    request = cursor.fetchone()

            # Save agent state
            self.state["last_hire_request"] = {
                "request_id": request["id"],
                "venue_id": venue_id,
                "status": "CONFIRMED"
            }

            self.save_state()

            return self._reply(
                message,
                Performative.AGREE,
                {
                    "request_id": request["id"],
                    "venue_id": venue_id,
                    "venue_name": venue["name"],
                    "status": "CONFIRMED",
                    "quoted_price": str(quoted_price),
                    "currency": "LKR"
                }
            )

        except (KeyError, TypeError, ValueError) as error:

            return self._reply(
                message,
                Performative.REFUSE,
                {
                    "reason": str(error)
                }
            )
