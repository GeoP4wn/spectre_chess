''' Since the Raspberry Pi is the orchestrator, you will need a Background Thread or an Asyncio Loop to handle the Online mode.

    The Main Loop: Keeps the Touchscreen responsive and checks local sensors.

    The Network Thread: Stays open to Lichess. When it hears a move, it puts it into a MoveQueue.

    The Manager: Checks the MoveQueue every cycle. If a move is there, it switches the system state to ROBOT_TURN.
'''
