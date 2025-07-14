# src/devices/lamp_post.py
import socket
import threading
import time
import uuid
from generated import smart_city_pb2

# --- Configurações ---
# Define um ID e tipo únicos para este dispositivo.
DEVICE_ID = f"lamp_{uuid.uuid4().hex[:6]}"
DEVICE_TYPE = smart_city_pb2.DeviceType.Value('LAMP_POST')
# As configurações do Gateway (IP, Porta TCP) foram removidas pois serão descobertas automaticamente.
MULTICAST_GROUP = "224.1.1.1"
MULTICAST_PORT = 5007

# --- Estado do Dispositivo ---
# Variável global para armazenar o estado atual do poste (ligado ou desligado).
is_on = False

def listen_for_commands(tcp_socket):
    """
    Escuta por comandos do Gateway na conexão TCP persistente.

    Esta função roda em uma thread dedicada e fica aguardando comandos para
    alterar o estado do poste de luz.
    """
    global is_on
    try:
        # Loop infinito para continuar recebendo comandos enquanto a conexão estiver ativa.
        while True:
            # Fica bloqueado aqui, esperando por dados do Gateway.
            data = tcp_socket.recv(1024)
            # Se não receber dados, significa que a conexão foi fechada pelo Gateway.
            if not data:
                print("Conexão com o Gateway perdida.")
                break
            
            # Decodifica a mensagem recebida usando Protocol Buffers.
            wrapper_msg = smart_city_pb2.WrapperMessage()
            wrapper_msg.ParseFromString(data)
            
            # Verifica se a mensagem é um comando e se é para este dispositivo específico.
            if wrapper_msg.HasField("command"):
                cmd = wrapper_msg.command
                if cmd.device_id == DEVICE_ID and cmd.HasField("toggle"):
                    # Inverte o estado booleano 'is_on'.
                    is_on = not is_on
                    print(f"--> Comando recebido! Poste de Luz ({DEVICE_ID}) agora está {'LIGADO' if is_on else 'DESLIGADO'}.")
    except ConnectionResetError:
        # Erro comum que ocorre quando o outro lado da conexão fecha abruptamente.
        print("Conexão com o Gateway foi resetada.")
    except Exception as e:
        print(f"Erro ao receber comando: {e}")
    finally:
        # Garante que o socket seja fechado em caso de erro ou desconexão.
        tcp_socket.close()

def discover_gateway_and_connect():
    """
    Escuta por anúncios do Gateway via multicast para descobrir seu IP e porta,
    e então estabelece uma conexão TCP para se registrar e receber comandos.
    """
    # Configura o socket para escutar por mensagens multicast.
    multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    multicast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    multicast_socket.bind(("", MULTICAST_PORT))
    group = socket.inet_aton(MULTICAST_GROUP)
    mreq = group + socket.inet_aton("0.0.0.0")
    multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    
    print(f"Poste de Luz ({DEVICE_ID}) aguardando anúncio do Gateway...")
    
    # Loop de descoberta.
    while True:
        data, address = multicast_socket.recvfrom(1024)
        
        wrapper_msg = smart_city_pb2.WrapperMessage()
        wrapper_msg.ParseFromString(data)
        
        # Se a mensagem recebida for um anúncio do Gateway...
        if wrapper_msg.HasField("gateway_info"):
            gateway_info = wrapper_msg.gateway_info
            discovered_ip = gateway_info.ip_address
            discovered_port = gateway_info.device_tcp_port
            
            print(f"--> Gateway encontrado em {discovered_ip}:{discovered_port}. Conectando...")
            
            try:
                # Inicia a CONEXÃO TCP PERSISTENTE com o Gateway.
                tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                tcp_socket.connect((discovered_ip, discovered_port))
                
                # Envia a mensagem de registro com suas informações.
                register_msg = smart_city_pb2.WrapperMessage()
                info = register_msg.device_info
                info.id = DEVICE_ID
                info.type = DEVICE_TYPE
                tcp_socket.send(register_msg.SerializeToString())
                
                print(f"--> SUCESSO: Registrado no Gateway. Aguardando comandos.")
                
                # Inicia a thread que ficará escutando por comandos na conexão estabelecida.
                command_thread = threading.Thread(target=listen_for_commands, args=(tcp_socket,), daemon=True)
                command_thread.start()
                # Sai do loop de descoberta, pois a conexão foi bem-sucedida.
                break

            except Exception as e:
                # Em caso de falha na conexão, aguarda 5 segundos antes de tentar novamente no próximo anúncio.
                print(f"Falha ao conectar no Gateway descoberto: {e}")
                time.sleep(5)

# Ponto de entrada do script.
if __name__ == "__main__":
    # Inicia o processo de descoberta e conexão.
    discover_gateway_and_connect()
    # Mantém a thread principal viva para que a thread de comandos em daemon possa continuar rodando.
    while True:
        time.sleep(3600)
