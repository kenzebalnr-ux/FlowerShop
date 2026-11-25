"""Locust 5/20/50/100 сценарийлері, сервер CPU/RAM бақылауы."""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
import time
import os
import tempfile
import threading
import psutil


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--host',default='http://127.0.0.1:8000')
    parser.add_argument('--server-pid',type=int)
    parser.add_argument('--start-server',action='store_true',help='Оқшау сынақ серверін 8010 портында іске қосу')
    parser.add_argument('--quick',action='store_true',help='Тек 5 пайдаланушы, 10 секунд; толық зертхананы алмастырмайды')
    args=parser.parse_args()
    output=Path('docs/results/load'); output.mkdir(parents=True,exist_ok=True)
    owned_server=None
    temporary=None
    if args.start_server:
        import uvicorn
        from backend.main import create_app
        temporary=tempfile.TemporaryDirectory(prefix='flowershop-load-',ignore_cleanup_errors=True)
        application=create_app('sqlite:///'+str(Path(temporary.name)/'load.db'))
        owned_server=uvicorn.Server(uvicorn.Config(application,host='127.0.0.1',port=8010,log_level='warning',access_log=False))
        server_thread=threading.Thread(target=owned_server.run,daemon=True)
        server_thread.start()
        import urllib.request
        args.host='http://127.0.0.1:8010'
        for attempt in range(100):
            try:
                with urllib.request.urlopen(args.host+'/api/health',timeout=1):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError('Сынақ сервері іске қосылмады')
        args.server_pid=os.getpid()
    if not args.server_pid:
        parser.error('--start-server немесе --server-pid қажет')
    server=psutil.Process(args.server_pid)
    scenarios=[(5,10)] if args.quick else [(5,60),(20,120),(50,180),(100,180)]
    summaries=[]
    for users,duration in scenarios:
        prefix=output/f'users-{users}'
        command=[sys.executable,'-X','utf8','-m','locust','-f','tests/locustfile.py','--headless','--host',args.host,'-u',str(users),'-r',str(users),'-t',f'{duration}s','--csv',str(prefix),'--csv-full-history','--stop-timeout','5','--only-summary']
        samples=[]; server.cpu_percent()
        with (output/f'users-{users}.log').open('w',encoding='utf-8') as log:
            process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
            while process.poll() is None:
                samples.append({'time':time.time(),'cpu_percent':server.cpu_percent(),'rss_mb':round(server.memory_info().rss/1024**2,2)})
                time.sleep(1)
        (output/f'users-{users}-resources.json').write_text(json.dumps(samples,indent=2),encoding='utf-8')
        stats_path=output/f'users-{users}_stats.csv'
        if not stats_path.exists():
            if owned_server:
                owned_server.should_exit=True
                server_thread.join(timeout=5)
                application.state.engine.dispose()
            raise RuntimeError(f'Locust нәтижесі жоқ. {output}/users-{users}.log файлын тексеріңіз')
        with stats_path.open(encoding='utf-8') as stats:
            rows=list(csv.DictReader(stats))
        total=next(row for row in rows if row['Name']=='Aggregated')
        summaries.append({'users':users,'duration_seconds':duration,'exit_code':process.returncode,
                          'requests':int(total['Request Count']),'failures':int(total['Failure Count']),
                          'average_ms':float(total['Average Response Time']),'p95_ms':float(total['95%']),
                          'rps':float(total['Requests/s']),'peak_cpu_percent':max(s['cpu_percent'] for s in samples),
                          'peak_rss_mb':max(s['rss_mb'] for s in samples)})
        (output/'summary.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(summaries[-1],ensure_ascii=False),flush=True)
    if owned_server:
        owned_server.should_exit=True
        server_thread.join(timeout=5)
        application.state.engine.dispose()
        temporary.cleanup()
    return 1 if any(s['exit_code'] for s in summaries) else 0


if __name__=='__main__':
    raise SystemExit(main())

