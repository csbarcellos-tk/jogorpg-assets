import requests

BASE_IMAGE_URL = "https://raw.githubusercontent.com/csbarcellos-tk/jogorpg-assets/main/images"

images_to_test = [
    f"{BASE_IMAGE_URL}/loja.png",
    f"{BASE_IMAGE_URL}/vendedor_ambulante.png",
    f"{BASE_IMAGE_URL}/vendedor_ambulante2.png"
]

print("Testando acesso às imagens no GitHub:\n")

for url in images_to_test:
    try:
        response = requests.head(url, timeout=5)
        if response.status_code == 200:
            print(f"✅ {url.split('/')[-1]}: OK")
        else:
            print(f"❌ {url.split('/')[-1]}: Status {response.status_code}")
            print(f"   URL: {url}")
    except Exception as e:
        print(f"❌ {url.split('/')[-1]}: Erro - {e}")
        print(f"   URL: {url}")

print("\n" + "="*60)
print("INSTRUÇÕES:")
print("1. Se todos os testes passaram (✅), as URLs estão corretas")
print("2. Se algum falhou (❌), verifique:")
print("   - As imagens foram commitadas no GitHub?")
print("   - Os nomes dos arquivos estão corretos (case-sensitive)?")
print("   - O repositório está público?")
print("="*60)
