"""Locust 5/20/50/100 сценарийлері, сервер CPU/RAM бақылауы."""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
import time
import psutil


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--host',default='http://127.0.0.1:8000')
    parser.add_argument('--server-pid',type=int,required=True)
    parser.add_argument('--quick',action='store_true',help='Тек 5 пайдаланушы, 10 секунд; толық зертхананы алмастырмайды')
    args=parser.parse_args()
    output=Path('docs/results/load'); output.mkdir(parents=True,exist_ok=True)
    server=psutil.Process(args.server_pid)
    scenarios=[(5,10)] if args.quick else [(5,60),(20,120),(50,180),(100,180)]
    summaries=[]
    for users,duration in scenarios:
        prefix=output/f'users-{users}'
        command=[sys.executable,'-m','locust','-f','tests/locustfile.py','--headless','--host',args.host,'-u',str(users),'-r',str(users),'-t',f'{duration}s','--csv',str(prefix),'--csv-full-history','--stop-timeout','5','--only-summary']
        samples=[]; server.cpu_percent()
        with (output/f'users-{users}.log').open('w',encoding='utf-8') as log:
            process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
            while process.poll() is None:
                samples.append({'time':time.time(),'cpu_percent':server.cpu_percent(),'rss_mb':round(server.memory_info().rss/1024**2,2)})
                time.sleep(1)
        (output/f'users-{users}-resources.json').write_text(json.dumps(samples,indent=2),encoding='utf-8')
        with (output/f'users-{users}_stats.csv').open(encoding='utf-8') as stats:
            rows=list(csv.DictReader(stats))
        total=next(row for row in rows if row['Name']=='Aggregated')
        summaries.append({'users':users,'duration_seconds':duration,'exit_code':process.returncode,
                          'requests':int(total['Request Count']),'failures':int(total['Failure Count']),
                          'average_ms':float(total['Average Response Time']),'p95_ms':float(total['95%']),
                          'rps':float(total['Requests/s']),'peak_cpu_percent':max(s['cpu_percent'] for s in samples),
                          'peak_rss_mb':max(s['rss_mb'] for s in samples)})
        (output/'summary.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(summaries[-1],ensure_ascii=False),flush=True)
    return 1 if any(s['exit_code'] for s in summaries) else 0


if __name__=='__main__':
    raise SystemExit(main())

