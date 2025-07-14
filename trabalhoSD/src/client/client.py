import socket
from generated import smart_city_pb2

# --- Configurações ---
# Certifique-se de que este IP e Porta correspondem ao seu Gateway
GATEWAY_IP = "192.168.1.7"
GATEWAY_PORT = 10003

def print_device_list(response_msg):
    """Função auxiliar para imprimir a lista de dispositivos de forma organizada."""
    if not response_msg.HasField("list_response"):
        print("[ERRO] Resposta inesperada do Gateway.")
        return
        
    print("\n--- Dispositivos Conectados ---")
    if not response_msg.list_response.devices:
        print("Nenhum dispositivo encontrado.")
    
    for device in response_msg.list_response.devices:
        device_type_name = smart_city_pb2.DeviceType.Name(device.type)
        print(f"  ID: {device.id} | Tipo: {device_type_name}")
    print("---------------------------------")

def main():
    """Função principal que executa o cliente."""
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((GATEWAY_IP, GATEWAY_PORT))
        print("Conectado ao Gateway. Bem-vindo ao Controle da Cidade Inteligente!")
    except Exception as e:
        print(f"Não foi possível conectar ao Gateway: {e}")
        return

    # Busca e exibe a lista inicial de dispositivos assim que conecta
    try:
        print("\nBuscando lista inicial de dispositivos...")
        request_msg = smart_city_pb2.WrapperMessage()
        request_msg.list_request.SetInParent()
        client_socket.send(request_msg.SerializeToString())
        
        response_data = client_socket.recv(4096)
        response_msg = smart_city_pb2.WrapperMessage()
        response_msg.ParseFromString(response_data)
        print_device_list(response_msg)
    except Exception as e:
        print(f"Erro ao buscar lista inicial: {e}")
        client_socket.close()
        return

    # Loop principal para interação com o usuário
    while True:
        print("\nOpções:")
        print("1. Listar dispositivos (Atualizar)")
        print("2. Ligar/Desligar um dispositivo (toggle)")
        print("3. Configurar resolução da Câmera")
        print("4. Configurar duração do Semáforo")
        print("5. Sair")
        choice = input("Escolha uma opção: ")

        try:
            if choice == '1':
                request_msg = smart_city_pb2.WrapperMessage()
                request_msg.list_request.SetInParent()
                client_socket.send(request_msg.SerializeToString())
                
                response_data = client_socket.recv(4096)
                response_msg = smart_city_pb2.WrapperMessage()
                response_msg.ParseFromString(response_data)
                print_device_list(response_msg)

            elif choice == '2':
                device_id = input("Digite o ID do dispositivo para ligar/desligar: ")
                command_msg = smart_city_pb2.WrapperMessage()
                cmd = command_msg.command
                cmd.device_id = device_id
                cmd.toggle = True
                client_socket.send(command_msg.SerializeToString())
                print(f"Comando de toggle enviado para o dispositivo {device_id}.")

            elif choice == '3':
                device_id = input("Digite o ID da Câmera: ")
                resolution = input("Digite a nova resolução (ex: FullHD, 4K): ")
                command_msg = smart_city_pb2.WrapperMessage()
                cmd = command_msg.command
                cmd.device_id = device_id
                cmd.new_config = f"resolution:{resolution}"
                client_socket.send(command_msg.SerializeToString())
                print(f"Comando de configuração enviado para a câmera {device_id}.")

            elif choice == '4':
                device_id = input("Digite o ID do Semáforo: ")
                duration = input("Digite a nova duração para o sinal vermelho (em segundos): ")
                command_msg = smart_city_pb2.WrapperMessage()
                cmd = command_msg.command
                cmd.device_id = device_id
                cmd.new_config = f"duration:{duration}"
                client_socket.send(command_msg.SerializeToString())
                print(f"Comando de configuração enviado para o semáforo {device_id}.")

            elif choice == '5':
                break
            else:
                print("Opção inválida.")
        except Exception as e:
            print(f"Erro durante a operação: {e}")
            break
    
    client_socket.close()
    print("Desconectado do Gateway.")

if __name__ == "__main__":
    main()