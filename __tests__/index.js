'use strict';

var chai = require('chai');
var getUsername = require('../lib/username.js');

var assert = chai.assert;

var IPC = require('../');

/*[
 'login@domain',
 'domain\login',
 'domain\\login',
 'domain/login',
 'domain//login'
 ].forEach(function (account) {

 });*/

describe('Username and domain parser', function () {
    describe('#getUsername()', function () {
        it('should return login from login', function () {
            assert.equal(getUsername('login'), 'login');
        });

        it('should return "login with space" from "login with space"', function () {
            assert.equal(getUsername('login with space'), 'login with space');
        });

        it('should return domain/login from login@domain', function () {
            assert.equal(getUsername('login@domain'), 'domain/login');
        });

        it('should return domain/login from domain\\login', function () {
            assert.equal(getUsername('domain\\login'), 'domain/login');
        });

        it('should return domain/login from domain/login', function () {
            assert.equal(getUsername('domain/login'), 'domain/login');
        });

        it('should return domain/login from domain//login', function () {
            assert.equal(getUsername('domain/login'), 'domain/login');
        });

        it('should return domain.name/login from login@domain.name', function () {
            assert.equal(getUsername('login@domain.name'), 'domain.name/login');
        });

        it('should return domain.name/login from domain.name\\login', function () {
            assert.equal(getUsername('domain.name\\login'), 'domain.name/login');
        });

        it('should return domain.name/login from domain.name/login', function () {
            assert.equal(getUsername('domain.name/login'), 'domain.name/login');
        });

        it('should return domain.name/login from domain.name//login', function () {
            assert.equal(getUsername('domain.name/login'), 'domain.name/login');
        });

        it.skip('should return domain/login@login from login@login@domain', function () {
            // TODO: use last @ in input string as delimiter
            assert.equal(getUsername('login@login@domain'), 'domain/login@login');
        });

        // not implemented
        it.skip('should return administr@tor@domain from domain\\administr@tor', function () {
            assert.equal(getUsername('administr@tor@domain'), 'domain\\administr@tor');
        });

        // not implemented
        it.skip('should return administr@tor@domain from domain/administr@tor', function () {
            assert.equal(getUsername('administr@tor@domain'), 'domain/administr@tor');
        });
    });
});

describe('Command testing', function() {
    var impacket = new IPC({
        username: 'admin@rvlab.net',
        password: '7aRQD3xg',
        host: '172.16.101.243'
    });
       
    impacket.run('ipconfig /all', function (err, result) {
        console.log(err || result);
    }); // */       
})