class EventAwacs:
    """
    Integrating real-time event awareness into your bot is a "pro-level" move. For a 15-delta strategy,
    an event like a Fed Rate Decision (FOMC) is a massive threat because it causes "IV Expansion"

    """

    def __init__(self):
        pass

    # def check_event_risk(self):
    #     # Fetch today's high-impact events
    #     calendar = EconomicCalendar.get_events(country='US', importance='high')
    #
    #     for event in calendar:
    #         if "Fed" in event['title'] or "FOMC" in event['title']:
    #             self._logger_.warning(
    #                 f"⚠️ EVENT ALERT | {event['title']} at {event['time']} | High Volatility Expected!")
    #             return True  # Signal the bot to stay flat
    #     return False

#     TODO Integrate this method to Raavan for getting the events and its impact
