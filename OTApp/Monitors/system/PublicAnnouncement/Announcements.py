import json
import queue
import threading


class PublicAnnouncement:
    def __init__(self, logger=None):
        self.logger = logger
        self.maintenance_scheduled = {"maintenance_scheduled": {}}
        self.product_updates = {"product_updates": {}}
        # The memory of the system: holding the product update and maintenance update
        self.announcement_update_queue = queue.Queue()
        # The dedicated spirit: processing in the background
        self.announcement_update_monitoring_thread = threading.Thread(
            target=self._announcement_update_monitoring_worker, daemon=True)
        self.announcement_update_monitoring_thread.start()

    def on_announcement(self, message):
        """
        Producer: Senses the announcement and pushes to memory.
        """
        self.announcement_update_queue.put(message)

    def _announcement_update_monitoring_worker(self):
        """
        Consumer: Dedicated thread to handle announcement update logic and retries.
        """
        while True:
            # Step 2: Retrieve fill from memory
            announcement_data = None
            try:
                announcement_data = self.announcement_update_queue.get()
                announcement_type = announcement_data.get('type')
                if announcement_type == 'system_status':
                    self.maintenance_scheduled.update(announcement_data)
                elif announcement_type == 'product_updates':
                    self.product_updates.update(announcement_data)
                elif announcement_type == 'subscriptions':
                    self.logger.info(f"Public Subscriptions announcement: {announcement_data}")
                elif announcement_type == 'mark_price':
                    self.logger.info(f"Mark Price announcement : {announcement_data}")
                else:
                    self.logger.error("Unknown announcement type: {}".format(announcement_type))
                    self.logger.info(f"Unknown announcement data: {announcement_data}")
            except Exception as e:
                self.logger.error(f"🚨 Announcement Update Monitor Thread Error: {str(e)}")
                # Optional: Re-queue the announcement if processing failed
                self.announcement_update_queue.put(announcement_data)
            finally:
                self.announcement_update_queue.task_done()  # Clean up memory reference
