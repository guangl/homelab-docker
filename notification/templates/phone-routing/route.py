import base64,json,logging,os,socket,struct,time,urllib.request
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
with open('/config/router.json') as f:C=json.load(f)
AUTH='Basic '+base64.b64encode((C['user']+':'+C['password']).encode()).decode()
def probe(timeout=2):
 try:
  i=os.getpid()&65535;q=int(time.monotonic()*1000)&65535;p=os.urandom(16);h=struct.pack('!BBHHH',8,0,0,i,q);b=h+p;n=sum(struct.unpack('!12H',b));n=(n>>16)+(n&65535);n+=(n>>16);pkt=struct.pack('!BBHHH',8,0,(~n)&65535,i,q)+p
  with socket.socket(socket.AF_INET,socket.SOCK_RAW,socket.IPPROTO_ICMP) as s:
   s.sendto(pkt,('192.168.10.100',0));end=time.monotonic()+timeout
   while time.monotonic()<end:
    s.settimeout(max(.01,end-time.monotonic()));d,a=s.recvfrom(4096);o=(d[0]&15)*4
    if a[0]=='192.168.10.100' and len(d)>=o+8:
     t,c,_,ii,qq=struct.unpack('!BBHHH',d[o:o+8])
     if t==0 and c==0 and ii==i and qq==q and d[o+8:]==p:return True
 except (OSError,ValueError):pass
 return False
def call(path,data):
 req=urllib.request.Request('http://apprise:8000/'+path,json.dumps(data).encode(),{'Authorization':AUTH,'Content-Type':'application/json','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=15) as r:return json.load(r)
def apply(channel):
 config='email = '+C[channel]+chr(10)
 if call('get/nas',{}).get('config')!=config:call('add/nas',{'config':config,'format':'text'})
 logging.info('phone_response=%s channel=%s',channel=='bark',channel)
def main():
 last=None
 while True:
  channel='bark' if probe() else 'mail'
  try:
   if channel!=last or call('get/nas',{}).get('config')!='email = '+C[channel]+chr(10):apply(channel)
   last=channel
  except Exception as e:
   logging.error('routing update failed (%s); retry email',type(e).__name__)
   try:apply('mail');last='mail'
   except Exception as e:logging.error('email routing unavailable (%s)',type(e).__name__)
  time.sleep(10)
if __name__=='__main__':main()
