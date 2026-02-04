from statemachine import StateMachine, State
# Entry point, state machine loop

'''
Modes:
1. BOOT (system startup, hardware checks, homing motors)
2. IDLE/MENU (Waiting for user login or game start)
3. HUMAN_TURN (Waiting for physical sensor changes)
4. ROBOT_TURN (calculating and executing mechanical movements)
5. ERROR (illegal move detect or hardware fault etc.)
6. GAME_OVER (display results, save stats)
'''

class ChessStateMachine(StateMachine):
    "State machine for Logic Flow"
    Boot = State()
    Idle = State()
    Human_Turn = State()
    Robot_Turn = State()
    Error = State()
    Game_Over = State()

    cycle = (
        Boot.to(Idle) |
        Idle.to(Human_Turn) |
        Human_Turn.to(Robot_Turn) |
        Robot_Turn.to(Human_Turn) |
        Human_Turn.to(Game_Over) |
        Robot_Turn.to(Game_Over) |
        (Human_Turn | Robot_Turn).to(Error) |
        Error.to(Idle)
    )

    def before_cycle():
        return 0
    
    def on_enter_Boot():
        return 0
    
    def on_enter_Idle():
        return 0
    
    def on_enter_Human_Turn():
        return 0
    
    def on_enter_Robot_Turn():
        return 0
    
    def on_enter_Game_Over():
        return 0

    def on_enter_Error():
        return 0
    
    
