import React, { useState, useEffect } from 'react';
import { Chess } from 'chess.js';
import { Chessboard } from 'react-chessboard';
import './App.css';

// WebSocket hook
function useWebSocket(url) {
  const [ws, setWs] = useState(null);
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);

  useEffect(() => {
    const socket = new WebSocket(url);

    socket.onopen = () => {
      console.log('WebSocket connected');
      setConnected(true);
    };

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log('Received:', data);
      setLastMessage(data);
    };

    socket.onclose = () => {
      console.log('WebSocket disconnected');
      setConnected(false);
    };

    socket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    setWs(socket);

    return () => {
      socket.close();
    };
  }, [url]);

  const sendMessage = (message) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message));
    }
  };

  return { ws, connected, lastMessage, sendMessage };
}

function App() {
  const [game, setGame] = useState(new Chess());
  const [fen, setFen] = useState(game.fen());
  const [gameInfo, setGameInfo] = useState(null);
  const [settings, setSettings] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [moveHistory, setMoveHistory] = useState([]);
  const [selectedSquare, setSelectedSquare] = useState(null);
  const [legalMoves, setLegalMoves] = useState([]);

  const { connected, lastMessage, sendMessage } = useWebSocket(
    `ws://${window.location.hostname}:8000/ws`
  );

  // Handle WebSocket messages
  useEffect(() => {
    if (!lastMessage) return;

    switch (lastMessage.type) {
      case 'init':
        if (lastMessage.game) {
          setGameInfo(lastMessage.game);
          setFen(lastMessage.game.fen);
          const newGame = new Chess(lastMessage.game.fen);
          setGame(newGame);
        }
        if (lastMessage.settings) {
          setSettings(lastMessage.settings);
        }
        break;

      case 'board_update':
        setFen(lastMessage.fen);
        const updatedGame = new Chess(lastMessage.fen);
        setGame(updatedGame);
        if (lastMessage.last_move) {
          setMoveHistory((prev) => [...prev, lastMessage.last_move]);
        }
        break;

      case 'settings_updated':
        setSettings(lastMessage.settings);
        break;

      case 'error':
        alert(lastMessage.message);
        break;

      case 'hint':
        highlightMove(lastMessage.move);
        break;

      default:
        break;
    }
  }, [lastMessage]);

  const highlightMove = (move) => {
    // TODO: Highlight the suggested move
    console.log('Hint:', move);
  };

  const onSquareClick = (square) => {
    if (selectedSquare) {
      // Try to make move
      const move = game.move({
        from: selectedSquare,
        to: square,
        promotion: 'q', // Always promote to queen for simplicity
      });

      if (move) {
        setFen(game.fen());
        setSelectedSquare(null);
        setLegalMoves([]);
        // Note: Actual move will be made by physical board
      } else {
        setSelectedSquare(square);
        showLegalMovesFor(square);
      }
    } else {
      setSelectedSquare(square);
      showLegalMovesFor(square);
    }
  };

  const showLegalMovesFor = (square) => {
    const moves = game.moves({ square, verbose: true });
    setLegalMoves(moves.map((move) => move.to));
  };

  const requestHint = () => {
    sendMessage({ type: 'request_hint' });
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>♟️ Spectre Chess</h1>
        <div className="connection-status">
          <span className={`status-dot ${connected ? 'connected' : 'disconnected'}`} />
          {connected ? 'Connected' : 'Disconnected'}
        </div>
      </header>

      <div className="main-container">
        <div className="board-container">
          <Chessboard
            position={fen}
            onSquareClick={onSquareClick}
            customSquareStyles={{
              ...legalMoves.reduce((acc, square) => {
                acc[square] = { backgroundColor: 'rgba(0, 255, 0, 0.3)' };
                return acc;
              }, {}),
              ...(selectedSquare ? { [selectedSquare]: { backgroundColor: 'rgba(255, 255, 0, 0.4)' } } : {}),
            }}
            boardWidth={500}
          />

          <div className="board-info">
            {gameInfo && (
              <>
                <div className="player-info">
                  <span className="player white">{gameInfo.white_player}</span>
                  <span className="vs">vs</span>
                  <span className="player black">{gameInfo.black_player}</span>
                </div>
                <div className="game-status">
                  <span>Turn: {gameInfo.current_turn}</span>
                  <span>Moves: {gameInfo.move_count}</span>
                </div>
              </>
            )}
          </div>
        </div>

        <div className="sidebar">
          <div className="controls">
            <button onClick={requestHint} className="btn btn-primary">
              💡 Get Hint
            </button>
            <button onClick={() => setShowSettings(!showSettings)} className="btn btn-secondary">
              ⚙️ Settings
            </button>
          </div>

          <div className="move-history">
            <h3>Move History</h3>
            <div className="moves">
              {moveHistory.map((move, idx) => (
                <div key={idx} className="move">
                  {Math.floor(idx / 2) + 1}. {move}
                </div>
              ))}
            </div>
          </div>

          {showSettings && settings && (
            <SettingsPanel settings={settings} onUpdate={(newSettings) => {
              fetch('/api/settings', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newSettings),
              });
              setSettings(newSettings);
            }} />
          )}
        </div>
      </div>
    </div>
  );
}

function SettingsPanel({ settings, onUpdate }) {
  const [localSettings, setLocalSettings] = useState(settings);

  const handleChange = (key, value) => {
    const updated = { ...localSettings, [key]: value };
    setLocalSettings(updated);
  };

  const saveSettings = () => {
    onUpdate(localSettings);
  };

  return (
    <div className="settings-panel">
      <h3>⚙️ Settings</h3>

      <div className="setting-group">
        <h4>Display</h4>

        <label>
          <input
            type="checkbox"
            checked={localSettings.leds_enabled}
            onChange={(e) => handleChange('leds_enabled', e.target.checked)}
          />
          LEDs Enabled
        </label>

        <label>
          LED Brightness
          <input
            type="range"
            min="0"
            max="255"
            value={localSettings.led_brightness}
            onChange={(e) => handleChange('led_brightness', parseInt(e.target.value))}
          />
          {localSettings.led_brightness}
        </label>

        <label>
          Theme
          <select
            value={localSettings.led_theme}
            onChange={(e) => handleChange('led_theme', e.target.value)}
          >
            <option value="CLASSIC">Classic</option>
            <option value="MODERN">Modern</option>
            <option value="RAINBOW">Rainbow</option>
          </select>
        </label>

        <label>
          <input
            type="checkbox"
            checked={localSettings.highlight_legal_moves}
            onChange={(e) => handleChange('highlight_legal_moves', e.target.checked)}
          />
          Highlight Legal Moves
        </label>

        <label>
          <input
            type="checkbox"
            checked={localSettings.highlight_last_move}
            onChange={(e) => handleChange('highlight_last_move', e.target.checked)}
          />
          Highlight Last Move
        </label>
      </div>

      <div className="setting-group">
        <h4>Move Evaluation</h4>

        <label>
          <input
            type="checkbox"
            checked={localSettings.evaluation_enabled}
            onChange={(e) => handleChange('evaluation_enabled', e.target.checked)}
          />
          Enable Evaluation
        </label>

        <label>
          <input
            type="checkbox"
            checked={localSettings.show_blunders}
            onChange={(e) => handleChange('show_blunders', e.target.checked)}
          />
          Show Blunders
        </label>

        <label>
          <input
            type="checkbox"
            checked={localSettings.show_mistakes}
            onChange={(e) => handleChange('show_mistakes', e.target.checked)}
          />
          Show Mistakes
        </label>

        <label>
          Hints per Game
          <input
            type="number"
            min="0"
            max="10"
            value={localSettings.hint_count}
            onChange={(e) => handleChange('hint_count', parseInt(e.target.value))}
          />
        </label>
      </div>

      <div className="setting-group">
        <h4>Engine</h4>

        <label>
          Difficulty (1-20)
          <input
            type="range"
            min="1"
            max="20"
            value={localSettings.engine_difficulty}
            onChange={(e) => handleChange('engine_difficulty', parseInt(e.target.value))}
          />
          {localSettings.engine_difficulty}
        </label>
      </div>

      <div className="setting-group">
        <h4>Motor</h4>

        <label>
          Speed
          <select
            value={localSettings.motor_speed}
            onChange={(e) => handleChange('motor_speed', e.target.value)}
          >
            <option value="SLOW">Slow</option>
            <option value="MEDIUM">Medium</option>
            <option value="FAST">Fast</option>
          </select>
        </label>
      </div>

      <div className="setting-group">
        <h4>Audio</h4>

        <label>
          <input
            type="checkbox"
            checked={localSettings.voice_enabled}
            onChange={(e) => handleChange('voice_enabled', e.target.checked)}
          />
          Voice Recognition
        </label>

        <label>
          <input
            type="checkbox"
            checked={localSettings.sound_enabled}
            onChange={(e) => handleChange('sound_enabled', e.target.checked)}
          />
          Sound Effects
        </label>

        <label>
          Volume
          <input
            type="range"
            min="0"
            max="100"
            value={localSettings.sound_volume}
            onChange={(e) => handleChange('sound_volume', parseInt(e.target.value))}
          />
          {localSettings.sound_volume}%
        </label>
      </div>

      <button onClick={saveSettings} className="btn btn-primary btn-block">
        Save Settings
      </button>
    </div>
  );
}

export default App;
