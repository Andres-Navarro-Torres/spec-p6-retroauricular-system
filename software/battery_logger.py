import serial
import serial.tools.list_ports
import csv
import time
from datetime import datetime
import sys

def main():
    print("=== SPEC-P6 | Prueba de Descarga de Batería Continua ===")
    
    # 1. Buscar puertos COM disponibles
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("Error: No se encontraron puertos COM. Conecta el Coordinator.")
        sys.exit()

    print("\nPuertos disponibles:")
    for i, p in enumerate(ports):
        print(f"[{i}] {p.device} - {p.description}")

    try:
        sel = int(input("\nSelecciona el número del puerto: "))
        port_name = ports[sel].device
    except (ValueError, IndexError):
        print("Selección inválida. Saliendo.")
        sys.exit()

    baud_rate = 921600
    
    # 2. Crear archivo CSV
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"SPEC_P6_BatteryTest_{timestamp_str}.csv"

    # Cabeceras basadas en master_node.ino
    headers = [
        "PC_Time", "SlaveID", "DeviceTimestamp_us", "Red", "IR", 
        "Ax", "Ay", "Az", "Gx", "Gy", "Gz", "Instant_Fs_Hz", "Battery_mV"
    ]

    try:
        ser = serial.Serial(port_name, baud_rate, timeout=1)
        print(f"\nConectado exitosamente a {port_name} a {baud_rate} baudios.")
        
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            print("Iniciando transmisión del nodo (enviando '1')...")
            ser.write(b'1')
            time.sleep(0.5) # Pequeña pausa para que el ESP-NOW reaccione
            
            print(f"\nGrabando datos continuamente en: {filename}")
            print(">>> PRESIONA Ctrl+C PARA DETENER LA GRABACIÓN <<<\n")
            
            samples_recorded = 0
            start_time = time.time()
            
            while True:
                if ser.in_waiting > 0:
                    # Leer línea y decodificar
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    
                    if line and line.count(',') == 11: # Validar que tenga exactamente 12 datos
                        parts = line.split(',')
                        pc_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                        
                        # Escribir directamente al disco duro
                        writer.writerow([pc_time] + parts)
                        f.flush() # Forzar guardado físico en disco
                        
                        samples_recorded += 1
                        
                        # Actualizar la consola cada 100 muestras para no alentar la terminal
                        if samples_recorded % 100 == 0:
                            elapsed = time.time() - start_time
                            battery_mv = parts[11]
                            print(f"Muestras: {samples_recorded} | Tiempo: {elapsed/60:.1f} min | Batería Nodo: {battery_mv} mV", end='\r')
                                
    except KeyboardInterrupt:
        print("\n\nGrabación detenida manualmente por el usuario (Ctrl+C).")
    except Exception as e:
        print(f"\nOcurrió un error inesperado: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            print("Apagando sensores del nodo (enviando '0')...")
            ser.write(b'0')
            ser.close()
        print(f"Prueba finalizada. Tu archivo está en: {filename}")

if __name__ == "__main__":
    main()