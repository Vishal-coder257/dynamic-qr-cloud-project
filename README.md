# Dynamic QR Code Service (Cloud Mini Project)

QR ke andar ek **short link** (`/r/<code>`) hota hai. Server us code ko database me dekhta hai aur user ko current destination par redirect karta hai.
Isliye QR print hone ke baad bhi destination badal sakte ho, aur scan count milta hai.

## Endpoints
| Method | Path | Kaam |
|---|---|---|
| GET | `/` | Web UI |
| POST | `/api/create` | `{"url": "..."}` -> code + QR |
| GET | `/r/<code>` | Redirect + scan count |
| PUT | `/api/update/<code>` | Destination badlo |
| GET | `/api/stats/<code>` | Scan count |
| GET | `/qr/<code>.png` | QR image |
| GET | `/health` | Health check (SLA/TTR ke liye) |

## 1. Local run (bina Docker)
```bash
pip install -r requirements.txt
python app.py        # http://localhost:5000
```

## 2. Docker
```bash
docker compose up --build -d
curl http://localhost:5000/health
docker ps            # STATUS me "healthy" dikhna chahiye
```

## 3. Load test (SLA: latency, throughput, availability)
```bash
locust -f locustfile.py --host http://localhost:5000 --headless -u 100 -r 10 -t 60s --csv results
```
`results_stats.csv` me average, P95, P99 latency aur requests/sec milega. Yahi numbers slide 10 me jayenge.

## 4. Failure injection + TTR
```bash
./ttr_test.sh http://localhost:5000 dynamic-qr
```
Output me Detection, Recovery, Verification aur total TTR seconds me aayega (slide 9 aur 10 ke liye). 3-4 baar chalake average le lo.

## 5. AWS deployment (EC2 + ECR)
Pehle AWS CLI configure karo (`aws configure`) ya AWS Academy ke credentials use karo. Region apni choose karo (jaise `ap-south-1`).

```bash
# 1) ECR repo + image push
aws ecr create-repository --repository-name dynamic-qr --region ap-south-1
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin $ACCOUNT.dkr.ecr.ap-south-1.amazonaws.com
docker build -t dynamic-qr .
docker tag dynamic-qr:latest $ACCOUNT.dkr.ecr.ap-south-1.amazonaws.com/dynamic-qr:latest
docker push $ACCOUNT.dkr.ecr.ap-south-1.amazonaws.com/dynamic-qr:latest
```

**EC2 launch (console se):**
1. Amazon Linux 2023, `t3.micro` (ya free-tier eligible type).
2. Security Group: port 22 (sirf My IP), port 5000 ya 80 (Anywhere).
3. IAM role attach karo jisme `AmazonEC2ContainerRegistryReadOnly` policy ho.

**EC2 ke andar (SSH karke):**
```bash
sudo dnf install -y docker && sudo systemctl enable --now docker
ACCOUNT=<tumhara-account-id>
aws ecr get-login-password --region ap-south-1 | sudo docker login --username AWS --password-stdin $ACCOUNT.dkr.ecr.ap-south-1.amazonaws.com
sudo docker run -d --name dynamic-qr --restart always -p 80:5000 \
  -e BASE_URL=http://<EC2-PUBLIC-IP> -v qr_data:/data \
  $ACCOUNT.dkr.ecr.ap-south-1.amazonaws.com/dynamic-qr:latest
```
Phir browser me `http://<EC2-PUBLIC-IP>` kholo.

## 6. CloudWatch monitoring
- EC2 ke CPU alarm: CloudWatch -> Alarms -> EC2 -> `CPUUtilization > 70%`.
- Status check alarm: `StatusCheckFailed` par alarm + (optional) auto-recover action.
- Route 53 ya ALB health check `/health` par lagao.
- Docker logs CloudWatch me bhejne ke liye `--log-driver=awslogs` use kar sakte ho.

## 7. Kharcha bachao
Demo ke baad EC2, ALB aur baaki resources **terminate/delete** karo. AWS Budgets me alert lagao.

## Notes
- Abhi database SQLite hai (Docker volume `/data` me). Production ke liye RDS ya DynamoDB aur limits ke liye Redis cache future work me daal sakte ho.
- Short code 6 random alphanumeric chars ka hai; sirf `http/https` URLs allowed hain.
