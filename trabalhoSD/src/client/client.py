import socket
import time
from generated import smart_city_pb2

# --- Configurações ---
# O IP e a Porta do Gateway foram removidos, pois serão descobertos automaticamente.
# As únicas constantes necessárias são as de multicast.
MULTICAST_GROUP = "224.1.1.1"
MULTICAST_PORT = 5007

def print_device_list(response_msg):
    """
    Função auxiliar para imprimir a lista de dispositivos de forma organizada.
    
    Recebe uma mensagem de resposta do gateway, verifica se ela contém uma lista
    de dispositivos e a imprime no console de forma legível.
    """
    if not response_msg.HasField("list_response"):
        print("[ERRO] Resposta inesperada do Gateway.")
        return
        
    print("\n--- Dispositivos Conectados ---")
    if not response_msg.list_response.devices:
        print("Nenhum dispositivo encontrado.")
    
    # Itera sobre cada dispositivo na resposta e imprime suas informações.
    for device in response_msg.list_response.devices:
        device_type_name = smart_city_pb2.DeviceType.Name(device.type)
        print(f"  ID: {device.id} | Tipo: {device_type_name}")
    print("---------------------------------")

def discover_gateway():
    """
    Escuta por anúncios do Gateway via multicast para descobrir seu IP e a porta do cliente.
    Retorna o IP e a Porta do cliente descobertos.
    """
    # Configura o socket para escutar por mensagens multicast.
    multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    multicast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    multicast_socket.bind(("", MULTICAST_PORT))
    group = socket.inet_aton(MULTICAST_GROUP)
    mreq = group + socket.inet_aton("0.0.0.0")
    multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    
    print("Procurando pelo Gateway na rede...")
    
    # Loop para aguardar o anúncio do Gateway.
    while True:
        # Fica bloqueado aqui até receber uma mensagem multicast.
        data, address = multicast_socket.recvfrom(1024)
        
        # Decodifica a mensagem recebida.
        wrapper_msg = smart_city_pb2.WrapperMessage()
        wrapper_msg.ParseFromString(data)
        
        # Se a mensagem for um anúncio do Gateway, extrai as informações.
        if wrapper_msg.HasField("gateway_info"):
            gateway_info = wrapper_msg.gateway_info
            discovered_ip = gateway_info.ip_address
            # O cliente usa a porta específica para clientes, anunciada pelo Gateway.
            discovered_port = gateway_info.client_tcp_port
            
            print(f"--> Gateway encontrado em {discovered_ip}:{discovered_port}.")
            multicast_socket.close() # Fecha o socket de descoberta.
            return discovered_ip, discovered_port # Retorna os dados encontrados.

def main():
    """Função principal que executa o cliente, desde a descoberta até a interação."""
    
    # --- ETAPA 1: DESCOBERTA ---
    # Primeiro, descobre o gateway na rede antes de qualquer outra coisa.
    gateway_ip, gateway_port = discover_gateway()
    
    # Se não encontrar o Gateway, encerra o programa.
    if not gateway_ip:
        print("Não foi possível encontrar o Gateway. Encerrando.")
        return

    # --- ETAPA 2: CONEXÃO ---
    # Tenta estabelecer a conexão TCP com os dados descobertos.
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((gateway_ip, gateway_port))
        print("Conectado ao Gateway. Bem-vindo ao Controle da Cidade Inteligente!")
    except Exception as e:
        print(f"Não foi possível conectar ao Gateway: {e}")
        return

    # --- ETAPA 3: BUSCA INICIAL DE ESTADO ---
    # Após conectar, busca e exibe a lista inicial de dispositivos.
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

    # --- ETAPA 4: LOOP DE INTERAÇÃO ---
    # Loop principal para interação com o usuário.
    while True:
        # Exibe o menu de opções.
        print("\nOpções:")
        print("1. Listar dispositivos (Atualizar)")
        print("2. Ligar/Desligar um dispositivo (toggle)")
        print("3. Configurar resolução da Câmera")
        print("4. Configurar duração do Semáforo")
        print("5. Sair")
        choice = input("Escolha uma opção: ")

        try:
            # Lógica para tratar a escolha do usuário.
            if choice == '1':
                # Envia um pedido para atualizar a lista de dispositivos.
                request_msg = smart_city_pb2.WrapperMessage()
                request_msg.list_request.SetInParent()
                client_socket.send(request_msg.SerializeToString())
                
                response_data = client_socket.recv(4096)
                response_msg = smart_city_pb2.WrapperMessage()
                response_msg.ParseFromString(response_data)
                print_device_list(response_msg)

            elif choice == '2':
                # Envia um comando de 'toggle'.
                device_id = input("Digite o ID do dispositivo para ligar/desligar: ")
                command_msg = smart_city_pb2.WrapperMessage()
                cmd = command_msg.command
                cmd.device_id = device_id
                cmd.toggle = True
                client_socket.send(command_msg.SerializeToString())
                print(f"Comando de toggle enviado para o dispositivo {device_id}.")

            elif choice == '3':
                # Envia um comando de configuração para a câmera.
                device_id = input("Digite o ID da Câmera: ")
                resolution = input("Digite a nova resolução (ex: FullHD, 4K): ")
                command_msg = smart_city_pb2.WrapperMessage()
                cmd = command_msg.command
                cmd.device_id = device_id
                cmd.new_config = f"resolution:{resolution}"
                client_socket.send(command_msg.SerializeToString())
                print(f"Comando de configuração enviado para a câmera {device_id}.")

            elif choice == '4':
                # Envia um comando de configuração para o semáforo.
                device_id = input("Digite o ID do Semáforo: ")
                duration = input("Digite a nova duração para o sinal vermelho (em segundos): ")
                command_msg = smart_city_pb2.WrapperMessage()
                cmd = command_msg.command
                cmd.device_id = device_id
                cmd.new_config = f"duration:{duration}"
                client_socket.send(command_msg.SerializeToString())
                print(f"Comando de configuração enviado para o semáforo {device_id}.")

            elif choice == '5':
                # Encerra o loop e o programa.
                break
            else:
                print("Opção inválida.")
        except Exception as e:
            print(f"Erro durante a operação: {e}")
            break
    
    # --- ETAPA 5: ENCERRAMENTO ---
    # Fecha a conexão com o Gateway ao sair do loop.
    client_socket.close()
    print("Desconectado do Gateway.")

# Ponto de entrada do script.
if __name__ == "__main__":
    main()
