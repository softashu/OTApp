1. AI integration with less than 2 sec latency for observe the live market and inform program
   to proceed or not with proper reason and action... use partially build AI class OTApp/AI/Raavan.py
2. Topup the MeanReversionStrategy for down trend
3. TODO : if market condition found after 3 PM IST is too much well ,
   then try to start strangle in next day after verification as there should not
   any calendar event / events that impact for example

   strangle_points 5
    - CRITICAL - Order Block : ✅ 💎 💎 💎 💎 💎 💎 Ultimate++ Green Light ON Strangle is high probability.
    - CRITICAL - Order Block : ✅ 💎 💎 💎 💎 Green Light ON Strangle is high probability.
    - INFO - 👉 ACTION: OB-Safe to Enter 0.15 Delta Strangle
    - CRITICAL - Super Trend : ✅ 💎 💎 💎 💎 💎 Ultimate Green Light ON Strangle is high probability.
    - INFO - Super Trend : ✅ 💎 💎 💎 Super conditions Strangle is high probability.
    - CRITICAL - ⏸️ ⏸️ SuperTrend + ADX : BEARISH_SIDEWAYS_CONFIRM on 1h time frame
    - ⏸️ SuperTrend : BEARISH_SIDEWAYS , Flatness :True on 1h time frame
    - INFO - +RSI : ✅ 💎 💎 Perfect conditions. Delta 0.15 Strangle is high probability.
    - INFO - +SMA Slope: ✅ 💎 Stable conditions. Delta 0.15 Strangle is high probability.

All message should print then you may invoke next day trade Note : verify if events not exit that day

4. TODO : multiple containerization one for websocket , and every stratetgy should have
   run on separate one container so logs are per container based.
   4,1 Need to trade of between establish the communication between containers via

    1. The Lightweight Cache: Redis (Recommended)
       Why it's likely your best fit:
       Redis is the industry standard for this. It serves as a high-speed "message bus" rather than just a database.
       Using Redis Pub/Sub or Redis Streams, the WebSocket container can "publish" a fill event, and the strategy
       container "subscribes" to it instantly.

       Pros: Extremely low latency (sub-millisecond), handles "1-to-many" (e.g., if you add a logging container later),
       and provides a buffer so the strategy container isn't overwhelmed.

       Latency: ~0.1ms to 0.5ms.

       Best for: Real-time trading signals where you want to decouple the "receiver" from the "executor."

    2. Shared Memory / Unix Domain Sockets (The "Speed Demon")
       If your strategy is "15-delta" and requires microsecond-level precision, you can bypass the network stack
       entirely. Docker allows you to share a volume containing a Unix Domain Socket or use Shared Memory (/dev/shm).

       Mechanism: Mount a shared volume to both containers. Use a socket file (like /tmp/orders.sock) for communication.

       Pros: No TCP/IP overhead. This is the fastest possible way for two processes to talk on the same machine.

       Cons: Harder to scale if you ever move the containers to separate EC2 instances.

       Latency: < 0.1ms.
       
   **Choose between 1 and 2** 