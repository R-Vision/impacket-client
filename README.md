# impacket-client
Wrapper around the impacket for node.js

### Install
```bash
npm install impacket-client
```

### Usage
```javascript
var IPC = require('impacket-client');

var impacket = new IPC({
    username: 'LOGIN',
    password: 'PASSWORD',
    host: 'IP-ADDRESS',
    timeout: 60000 // optional timeout in ms, winexe process will be killed with SIGKILL
});

// Run command on remote host
impacket.run('cmd.exe /c ipconfig /all', function (err, stdout, stderr) {
    // console.log(stdout);
});
```

### Development roadmap
 * v0.1.0 - Winexe-inspired console client
 * v0.2 - running Impacket as a service without need to reinstall services each time
