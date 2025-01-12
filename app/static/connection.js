

class WebSocketConnection {
  
  constructor(host, port) {
    
    this.instructions = {} 
    this.connected = false
    this.host = host
    this.port = port
  }

  connect() {
    this.socket = new WebSocket('ws://' + this.host + ':' + this.port)
    
    this.socket.onmessage = event => this._on_message(this.instructions, event)
    this.socket.onclose = event => this._on_close(event)
    this.socket.onerror = event => this._on_error(event)
    this.socket.onopen = event => this._on_open(event)
  }
  
  register_instruction(tag, func){
    this.instructions[tag] = func
  }

  send_instruction(tag, data) {
    this.socket.send(tag + ":" + JSON.stringify(data))
  }

  _on_open(event) {
    this.connected = true
  }


  _on_message(instructions, event) {

    let idx = 0
    while(idx < event.data.length && event.data[idx] != ":") idx++;

    const instr = event.data.substring(0, idx)
    const data = event.data.substring(idx + 1)

    let json_data = data ? JSON.parse(data) : null
    instructions[instr](json_data)
  }

  _on_close(event) {
    this.connected = false
    this.connect()
  }

  _on_error(event) {

  }
}


export default WebSocketConnection;