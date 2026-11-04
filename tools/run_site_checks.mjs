// Shared test launcher: supply Python's site module path without shell setup.
import {spawn} from 'node:child_process';
import {resolve} from 'node:path';
const args=process.argv.slice(2);
const child=spawn(resolve('.venv/Scripts/python.exe'),args.length?args:
 ['-m','unittest','discover','-s','tests','-t','.','-q'],
 {env:{...process.env,PYTHONPATH:'site',PYTHONIOENCODING:'utf-8'},stdio:'inherit',windowsHide:true});
child.on('error',error=>{console.error(error);process.exitCode=1});
child.on('exit',code=>{process.exitCode=code??1});
