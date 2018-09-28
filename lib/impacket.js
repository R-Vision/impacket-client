'use strict';

var path = require('path');
var spawn = require('child_process').spawn;
var events = require('events');
var sh = require('shelljs');
var rl = require('readline');
var devnull = require('dev-null');

var getUsername = require('./username.js');

/**
 * IPC - Impacker Client Class
 * @param options
 * @returns {IPC}
 * @constructor
 */
function IPC(options) {
    this.host = options.host;
    this.username = getUsername(options.username);
    this.password = options.password;
    this.options = options;

    //if (sh.which('psexec.py')) {
    //    this.winexe = sh.which('psexec.py');
    //} else if (process.platform === 'linux' && process.arch === 'x64') {
        this.winexe = path.join(__dirname, '../', 'psexec', 'psexec.py');
    //}

    events.EventEmitter.call(this);

    return this;
}

IPC.super_ = events.EventEmitter;

IPC.prototype = Object.create(events.EventEmitter.prototype, {
    constructor: {
        value: IPC,
        enumerable: false
    }
});

/**
 * Return args for winexe or psexec
 * @private
 */
IPC.prototype._getArgs = function () {
    var args = [];

    if (!this.password) {
        args.push('-no-pass');
    }

    if (this.options) {
        if (this.options.reinstall) {
            args.push('--reinstall');
        }

        if (this.options.uninstall) {
            args.push('--uninstall');
        }

        if (this.options.system) {
            args.push('--system');
        }
    }

    if (this.username) {
        if (this.password) {
            args.push(this.username + ':' + this.password + '@' + this.host);
        } else {
            args.push(this.username + '@' + this.host);
        }
    }

    args.push(this.cmd);

    return args;
};


/**
 * Spawn winexe or psexec with arguments
 * @param callback
 * @private
 */
IPC.prototype._exec = function (callback) {
    var self = this;
    var stdio = (this.isWindows) ? ['ignore', 'pipe', 'pipe'] : undefined;

    const options = {
        cwd: path.join(__dirname, '..'),
        stdio: stdio
    };

    if (process.platform === 'win32') {
        options.shell = true;
    }

    //console.log(this.winexe);

    var cp = spawn(this.winexe, this._getArgs(), options);

    var stdoutRL = rl.createInterface({input: cp.stdout, output: devnull()});
    var stderrRL = rl.createInterface({input: cp.stderr, output: devnull()});

    var stdout = '';
    var watchDog;

    if (this.options.timeout) {
        watchDog = setTimeout(function () {
            try {
                process.kill(cp.pid, 'SIGKILL');
            } catch (e) {}
        }, this.options.timeout);
    }

    stdoutRL.on('line', function (data) {
        stdout += data + '\n';
        self.emit('stdout', data);
    });

    var stderr = '';

    stderrRL.on('line', function (data) {
        stderr += data + '\n';
        self.emit('stderr', data);
    });

    cp.on('error', function (err) {
        if (watchDog) {
            clearTimeout(watchDog);
        }
        self.emit('error', err);
    });

    cp.on('close', function (code) {
        if (watchDog) {
            clearTimeout(watchDog);
        }
        if (code !== 0) {
            callback(new Error('Exit code: ' + code + '. ' + stderr.trim()), stdout, stderr);
        } else {
            callback(null, stdout, stderr);
        }
    });
};

/**
 * Run
 * @param cmd
 * @param options
 * @param callback
 * @returns {WinExe}
 */
IPC.prototype.run = function (cmd, options, callback) {
    this.cmd = cmd;

    if (typeof options === 'function') {
        callback = options;
    } else {
        this.options = options || {};
    }

    if (typeof callback !== 'function') {
        callback = function () {
        };
    }

    this._exec(callback);

    return this;
};

module.exports = IPC;
