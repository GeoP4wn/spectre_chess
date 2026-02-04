import asyncio
from statemachine import StateMachine, State
from game_manager import GameManager
from hardware_interface import HardwareInterface
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
    Boot = State(initial=True)
    Idle = State()
    Human_Turn = State()
    Robot_Thinking = State()
    Robot_Moving = State()
    Error = State()
    Game_Over = State()

    #define Transitions
    startup_complete = Boot.to(Idle)
    start_game = Idle.to(Human_Turn)

    move_processed = (
        Human_Turn.to(Robot_Thinking, cond="is_robot_next") |
        Human_Turn.to(Human_Turn, cond="is_human_next") |
        Robot_Moving.to(Human_Turn)
    )

    think_complete = Robot_Thinking.to(Robot_Moving)
    execution_done = Robot_Moving.to(Human_Turn)

    fail = (Human_Turn | Robot_Thinking | Robot_Moving).to(Error)
    #TODO : WHAT ABOUT FAILURE AT BOOT OR INIT?
    resolve = Error.to(Human_Turn)
    finish = (Human_Turn | Robot_Moving).to(Game_Over)


    
