from datetime import datetime

data = {
    "uuid": "테스트-UUID",
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "ip": "127.0.0.1",
    "seller_name": "테스트판매처",
    "keywords": "테스트키워드1, 테스트키워드2",
    "results_json": '{"테스트키워드1": "1위", "테스트키워드2": "3위"}'
}

print("테스트 데이터:")
for key, value in data.items():
    print(f"  {key}: {value}")
print("\n프로그램이 정상적으로 실행되었습니다.")
