# Preguntas y respuestas para la defensa

Guía de práctica para presentar Banco MNM en Redes e Infraestructura. Las respuestas describen la implementación actual; puedes adaptarlas a tu forma de hablar.

## 1. Idea del negocio y alcance

1. **¿Qué problema busca representar Banco MNM?**
   **Respuesta:** Simula operaciones bancarias básicas para practicar autenticación, autorización por roles, consultas de movimientos y transferencias entre cuentas.

2. **¿Quiénes son los usuarios y qué diferencia hay entre cliente y analista?**
   **Respuesta:** El cliente consulta su propia cuenta y puede transferir. El analista consulta indicadores agregados y alertas, pero no puede transferir ni ver historiales completos de clientes.

3. **¿Qué puede hacer un cliente?**
   **Respuesta:** Consultar saldo, ingresos, egresos, movimientos y destinatarios, y enviar dinero a otra cuenta habilitada.

4. **¿Qué puede hacer el analista?**
   **Respuesta:** Consultar resúmenes globales, actividad mensual y alertas de transacciones que superan un umbral. Sus permisos son de consulta.

5. **¿El sistema está conectado a un banco real o mueve dinero real?**
   **Respuesta:** No. Es una aplicación educativa con datos simulados; no procesa pagos ni se conecta a una entidad financiera.

6. **¿Por qué no deben usarse las cuentas demo en producción?**
   **Respuesta:** Tienen contraseñas conocidas y datos previsibles para facilitar pruebas. En un entorno real habría que desactivar la carga demo y gestionar credenciales seguras.

7. **¿Qué faltaría para convertirlo en un servicio bancario real?**
   **Respuesta:** Entre otras cosas, integración financiera autorizada, controles regulatorios, cifrado TLS, gestión segura de claves, auditoría, monitoreo, copias de seguridad, pruebas de seguridad y alta disponibilidad.

8. **¿El sistema está publicado en `bancomnm.xyz`?**
   **Respuesta:** No. Ese dominio solo aparece como sufijo de correos de demostración. La aplicación se usa localmente en `localhost:8080` con Docker Compose.

## 2. Arquitectura de la aplicación

9. **¿Cómo describirías la arquitectura general?**
   **Respuesta:** Es una arquitectura de servicios separados detrás de un gateway Nginx. El frontend se sirve como archivos estáticos, AUTH gestiona identidad, BANCO maneja las operaciones financieras simuladas y PostgreSQL almacena los datos.

10. **¿Qué servicios independientes componen el sistema?**
	**Respuesta:** `gateway` sirve el frontend y enruta solicitudes; `auth` gestiona usuarios y tokens; `bank` gestiona cuentas, transacciones y transferencias; `database` ejecuta PostgreSQL.

11. **¿Por qué separar AUTH y BANCO?**
	**Respuesta:** Para asignar responsabilidades distintas: identidad y emisión de tokens quedan en AUTH, mientras que los datos y reglas bancarias quedan en BANCO. Esto facilita desplegarlos y mantenerlos por separado, aunque aumenta la cantidad de componentes que hay que configurar y monitorear.

12. **¿Qué información administra cada API?**
	**Respuesta:** AUTH administra usuarios, hashes de contraseñas y roles. BANCO administra cuentas y transacciones.

13. **¿Qué función cumple Nginx?**
	**Respuesta:** Actúa como gateway: sirve el frontend y reenvía las llamadas API al servicio correspondiente.

14. **¿Cómo enruta Nginx las solicitudes?**
	**Respuesta:** Las rutas `/api/auth/` se envían a AUTH, que escucha en el puerto 8001. El resto de `/api/` se envía a BANCO, en el puerto 8002.

15. **¿Qué hace el frontend y cómo llama a las APIs?**
	**Respuesta:** Presenta el dashboard y las pantallas para los roles. Envía solicitudes HTTP al mismo origen de Nginx, que las dirige al backend adecuado.

16. **¿Qué significa que los servicios estén desacoplados?**
	**Respuesta:** Que cada servicio tiene una responsabilidad y un proceso de despliegue propios. Se pueden modificar por separado, pero hay que mantener correctamente sus direcciones, secretos, dependencias y disponibilidad.

17. **¿Qué se podría escalar por separado y cuál sería un límite?**
	**Respuesta:** En principio AUTH y BANCO podrían tener más instancias según su carga. La base de datos es un punto compartido y no se configura aquí con replicación o alta disponibilidad, por lo que podría limitar el crecimiento.

## 3. Redes y flujo de solicitudes

18. **Describe el recorrido de una petición.**
	**Respuesta:** El navegador llama a Nginx; Nginx sirve la página o reenvía la ruta a AUTH o BANCO. La API procesa la solicitud y, cuando necesita datos, se conecta a su base correspondiente en PostgreSQL.

19. **¿Cómo se localizan los servicios dentro de Docker Compose?**
	**Respuesta:** Compose crea una red privada y DNS interno. Los contenedores se comunican con nombres de servicio, como `auth`, `bank`, `database` y `namenode`, sin usar IPs fijas.

20. **¿Qué red utiliza Docker Swarm?**
	**Respuesta:** Swarm puede crear una red overlay entre nodos para conectar servicios distribuidos. En este proyecto la red del stack es overlay y los servicios con almacenamiento local se fijan al nodo etiquetado.

21. **¿Qué es publicar un puerto en Docker?**
	**Respuesta:** Es mapear un puerto del host al puerto de un contenedor o servicio. Compose publica la aplicación en `HTTP_PORT` (8080 por defecto); las APIs solo son accesibles desde localhost en el entorno de desarrollo.

22. **¿Qué puertos utiliza cada servicio?**
	**Respuesta:** Nginx escucha en el puerto 80 del contenedor; AUTH en 8001, BANCO en 8002 y PostgreSQL en 5432 dentro de la red. Compose publica Nginx en el puerto 8080 y expone las APIs solo en localhost para desarrollo.

23. **¿Por qué solo se publica el gateway?**
	**Respuesta:** Centraliza el acceso por un solo punto de entrada y evita exponer directamente las APIs y la base de datos al host. La configuración actual de Docker Compose tampoco publica sus puertos.

24. **¿Cómo se comunican los contenedores en Docker Compose?**
	**Respuesta:** Comparten la red creada por Compose y se encuentran por los nombres de servicio, como `auth`, `bank` y `database`, sin necesitar direcciones IP fijas.

25. **Si falla la comunicación entre Nginx y AUTH, ¿qué revisarías?**
	**Respuesta:** Revisaría que AUTH esté levantado y saludable, que escuche en 8001, que el nombre o IP configurado sea correcto, que haya conectividad entre las redes y que los logs de Nginx y AUTH no muestren errores.

26. **¿Qué hace `/health` y cuál es su limitación?**
	**Respuesta:** Ofrece una comprobación sencilla para saber si el gateway responde. En esta configuración devuelve una respuesta estática, así que por sí sola no confirma que AUTH, BANCO o PostgreSQL estén disponibles.

27. **¿Se necesita DNS público para esta entrega?**
	**Respuesta:** No. La aplicación se abre usando `localhost` desde el mismo equipo. No se ha configurado un dominio público ni un servicio DNS para publicarla.

28. **¿Se usa HTTP o HTTPS?**
	**Respuesta:** La configuración local usa HTTP. HTTPS cifra el tráfico y verifica la identidad del servidor mediante TLS; sería necesario configurarlo antes de exponer la aplicación en una red no confiable.

## 4. Infraestructura y despliegue

29. **¿Qué servicios ejecuta Docker Compose?**
	**Respuesta:** Ejecuta los servicios bancarios (Nginx, AUTH, BANCO y PostgreSQL), el clúster Hadoop con HDFS/YARN/MapReduce y Airflow con su base de metadatos.

30. **¿Qué diferencia hay entre Docker Compose y Docker Swarm?**
	**Respuesta:** Compose facilita levantar y operar el conjunto de contenedores en un host de desarrollo. Swarm programa servicios en nodos de un clúster, gestiona réplicas y usa una red overlay.

31. **¿Qué se escala en el stack Swarm?**
	**Respuesta:** AUTH y BANCO son servicios sin estado y se pueden replicar con `docker service scale`. Las bases de datos y los volúmenes Hadoop se mantienen con una réplica y almacenamiento local en esta configuración educativa.

32. **¿Qué hay que preparar antes de un despliegue Swarm?**
	**Respuesta:** Construir y publicar las imágenes de la aplicación y Airflow en un registry disponible para los nodos, cargar las variables de entorno y etiquetar el nodo que tendrá los volúmenes locales.

33. **¿Qué pasa con los datos al detener Docker Compose?**
	**Respuesta:** Los datos se guardan en el volumen `postgres_data`. `docker compose down` elimina los contenedores, pero conserva el volumen; `docker compose down -v` también lo elimina y borra permanentemente esos datos.

34. **¿Qué limitación tiene el almacenamiento en este Swarm?**
	**Respuesta:** Los volúmenes nombrados usan almacenamiento local del nodo; no son replicados por Swarm. Si el nodo se pierde, los datos pueden quedar inaccesibles. Para producción se requiere almacenamiento persistente externo y respaldos.

35. **¿Cómo comprobarías el estado y revisarías logs?**
	**Respuesta:** En Compose usaría `docker compose ps` y `docker compose logs`. En Swarm consultaría `docker stack services bancomnm`, `docker service ps` y `docker service logs`.

36. **Si modificas BANCO, ¿qué debes reconstruir o provisionar?**
	**Respuesta:** Reconstruiría la imagen de la aplicación y actualizaría los servicios AUTH/BANCO en Compose o Swarm. Si el cambio afecta código compartido, también podría afectar AUTH.

37. **¿Qué ventaja tiene cada método?**
	**Respuesta:** Compose ofrece un entorno reproducible de desarrollo; Swarm añade programación de tareas y réplicas entre nodos. Ninguno sustituye un diseño explícito de almacenamiento distribuido y alta disponibilidad.

## 5. Autenticación y seguridad

38. **¿Cómo se autentica un usuario?**
	**Respuesta:** Envía su correo y contraseña a AUTH. Si son válidos, AUTH devuelve un JWT con información de identidad, rol, cuenta asociada y expiración.

39. **¿Qué contiene el JWT y cómo se envía?**
	**Respuesta:** Incluye identificador del usuario, rol, `account_id` y tiempos de emisión y expiración. El cliente lo envía en la cabecera `Authorization: Bearer <token>`.

40. **¿Cómo valida BANCO el token sin llamar a AUTH?**
	**Respuesta:** Verifica localmente la firma y la expiración del JWT usando el secreto compartido. Por eso puede validar un token ya emitido sin consultar AUTH en cada solicitud.

41. **¿Por qué comparten el secreto de firma?**
	**Respuesta:** AUTH lo usa para firmar los tokens y BANCO para comprobar la firma. Si los valores no coinciden, BANCO rechazará los tokens como inválidos. El secreto debe ser privado y suficientemente fuerte.

42. **¿Cómo se guardan las contraseñas?**
	**Respuesta:** Se guarda un hash de contraseña, no el texto original. El hash dificulta recuperar la contraseña a partir del dato almacenado; durante el login se verifica la contraseña contra ese hash.

43. **¿Cómo se aplican los permisos por rol?**
	**Respuesta:** BANCO valida el JWT y comprueba el rol requerido en cada ruta. Por ejemplo, las rutas de cliente requieren el rol `cliente` y las rutas globales requieren `analista`.

44. **¿Cómo se evita operar sobre la cuenta de otra persona?**
	**Respuesta:** BANCO obtiene la cuenta de origen desde el token validado, no de un ID enviado por el navegador. También limita las consultas al `account_id` del usuario y comprueba permisos antes de ejecutar acciones.

45. **¿Qué secretos se configuran en `.env` y por qué no deben subirse a Git?**
	**Respuesta:** Principalmente la contraseña de PostgreSQL y `JWT_SECRET`. Si se publican, otra persona podría acceder a la base o firmar tokens válidos; por eso `.env` debe mantenerse privado.

46. **¿Qué riesgo tiene guardar el token en el almacenamiento local del navegador?**
	**Respuesta:** Si un ataque de JavaScript, como XSS, logra ejecutarse en la página, podría leer el token. Para producción habría que revisar el almacenamiento, prevenir XSS y aplicar otras medidas de seguridad.

47. **¿Qué cambiarías antes de exponerlo a Internet?**
	**Respuesta:** Configuraría HTTPS, secretos fuertes y protegidos, credenciales no demo, reglas de firewall, gestión y rotación de claves, monitoreo, respaldos, controles de acceso y una revisión de seguridad. También evaluaría una infraestructura con redundancia.

## 6. Base de datos y transferencias

48. **¿Hay dos bases de datos o dos servidores PostgreSQL?**
	**Respuesta:** Hay dos bases lógicas, `auth_db` y `banco_db`, dentro de un servicio PostgreSQL. No son dos servidores PostgreSQL independientes en esta configuración.

49. **¿Qué tablas principales contiene cada base?**
	**Respuesta:** `auth_db` contiene `usuarios`. `banco_db` contiene `cuentas` y `transacciones`.

50. **¿Por qué `usuarios.account_id` no es una clave foránea?**
	**Respuesta:** Porque usuarios y cuentas viven en bases separadas. Una clave foránea relacional normal no puede garantizar esa relación entre las dos bases; AUTH mantiene el identificador asociado en su registro.

51. **¿Qué representa un registro de `transacciones`?**
	**Respuesta:** Representa un movimiento asociado a una cuenta, con fecha, tipo de movimiento, importe, operación, categoría y saldo resultante.

52. **¿Cómo se calcula el saldo mostrado?**
	**Respuesta:** BANCO consulta el `balance_after` del movimiento más reciente de la cuenta. Por eso cada movimiento guarda el saldo resultante.

53. **¿Qué valida BANCO antes de una transferencia?**
	**Respuesta:** Comprueba que el usuario tenga una cuenta asociada, que el destinatario exista, que no sea la misma cuenta y que haya saldo suficiente. También valida que el importe tenga formato y valor permitidos.

54. **¿Cómo se registra una transferencia atómicamente?**
	**Respuesta:** BANCO crea un débito para la cuenta de origen y un crédito para la cuenta destino dentro de una única transacción PostgreSQL. Si la operación falla antes del commit, los cambios no deben quedar aplicados parcialmente.

55. **¿Para qué se bloquean las cuentas durante la transferencia?**
	**Respuesta:** Los bloqueos de fila ayudan a coordinar transferencias concurrentes y evitar que dos operaciones lean y gasten al mismo tiempo un saldo desactualizado. El código bloquea las cuentas en orden para reducir el riesgo de interbloqueo.

56. **¿Qué debe ocurrir si falla la escritura del crédito?**
	**Respuesta:** Debe revertirse la transacción completa, incluido el débito, para que no se descuente dinero sin acreditarlo al destinatario.

57. **¿Qué validaciones tiene el importe y qué errores se esperan?**
	**Respuesta:** Debe ser mayor que cero y admite como máximo dos decimales, además de estar dentro de los límites definidos. Un destinatario inexistente produce un error de no encontrado y un saldo insuficiente produce un error de solicitud inválida.

58. **¿Para qué sirven índices y paginación?**
	**Respuesta:** Los índices aceleran filtros y búsquedas frecuentes, como las transacciones por cuenta, fecha o tipo. La paginación limita cuántos registros se devuelven en una respuesta y evita cargar todo el historial de una vez.

## 7. Pruebas, fallos y evolución

59. **¿Qué prueban las pruebas automatizadas y por qué usan SQLite temporal?**
	**Respuesta:** Ejecutan pruebas de las APIs en un entorno aislado, sin levantar todos los servicios. SQLite temporal simplifica las pruebas y evita modificar las bases PostgreSQL del despliegue; no sustituye pruebas de integración de toda la red.

60. **¿Cómo demostrarías que un cliente no puede entrar a rutas de analista?**
	**Respuesta:** Iniciaría sesión como cliente, llamaría a una ruta de analista con su JWT y comprobaría que la API responde con acceso prohibido. También probaría una ruta privada sin token y esperaría una respuesta de no autorizado.

61. **El healthcheck responde, pero el login falla. ¿Qué revisarías?**
	**Respuesta:** Revisaría los logs y el estado de AUTH, la conexión a `auth_db`, las variables de entorno, el secreto JWT y las credenciales usadas. El healthcheck del gateway solo confirma que Nginx responde, no que el login funcione.

62. **La interfaz carga, pero `/api` devuelve errores. ¿Qué revisarías?**
	**Respuesta:** Revisaría las reglas `location` de Nginx, la conectividad y estado de AUTH o BANCO, los puertos y nombres de servicio, y después los logs de la API que debía recibir la petición.

63. **¿Qué pasa si PostgreSQL deja de responder?**
	**Respuesta:** Las operaciones de AUTH o BANCO que necesiten consultar o guardar datos fallarán. Los healthchecks de las APIs deberían reflejar el problema si comprueban dependencias, pero el `/health` estático del gateway puede seguir respondiendo.

64. **¿Cómo diseñarías respaldos y recuperación?**
	**Respuesta:** Programaría copias de seguridad periódicas de ambas bases, las almacenaría fuera de la VM o del host principal, protegería su acceso y probaría restauraciones regularmente. Un volumen persistente por sí solo no es un respaldo.

65. **¿Qué mejoras harías para producción?**
	**Respuesta:** Añadiría monitoreo y alertas, logs centralizados, respaldos comprobados, TLS, gestión de secretos, redundancia de servicios y base de datos, despliegues automatizados y pruebas de carga y seguridad.

## Escenarios para practicar

- **El usuario inicia sesión, pero falla el resumen. ¿Qué revisarías?**
  **Respuesta:** Confirmaría que el token se envíe y no esté expirado; comprobaría que Nginx dirija `/api/` a BANCO; revisaría estado, logs y conexión de BANCO con `banco_db`.

- **AUTH se reinicia mientras BANCO sigue activo. ¿Qué pasa con los usuarios conectados?**
  **Respuesta:** BANCO puede seguir validando tokens ya emitidos mientras sean válidos, porque comprueba su firma localmente. No se podrán iniciar nuevas sesiones hasta que AUTH vuelva a estar disponible. Esto depende de que BANCO tenga el mismo secreto JWT.

- **Dos transferencias salen al mismo tiempo de una cuenta con saldo limitado. ¿Qué riesgo existe?**
  **Respuesta:** Sin coordinación, ambas podrían leer el mismo saldo y aprobar importes que juntas lo superen. Los bloqueos de las filas de cuenta y la transacción buscan serializar esa parte y evitar actualizaciones inconsistentes.

- **Se elimina `postgres_data`. ¿Qué se pierde?**
  **Respuesta:** Se eliminan los datos persistidos por PostgreSQL de Docker Compose. Para recuperarlos hace falta restaurar una copia de seguridad; por eso conviene guardar respaldos fuera del volumen.

- **El profesor intenta abrir un puerto interno desde otro equipo. ¿Por qué podría fallar?**
  **Respuesta:** Los servicios internos no publican todos sus puertos en el host. En Swarm, además, el firewall y las redes overlay controlan qué tráfico entra al clúster.

- **Te piden publicar el sistema en Internet. ¿Qué revisarías primero?**
  **Respuesta:** No bastaría con abrir un puerto: configuraría DNS y HTTPS, firewall y proxy, secretos y credenciales nuevas, eliminaría datos demo, añadiría monitoreo y respaldos y revisaría disponibilidad, privacidad y seguridad.

## Datos rápidos para memorizar

- **AUTH:** usuarios, contraseñas con hash y emisión de JWT.
- **BANCO:** cuentas, movimientos, roles y transferencias simuladas.
- **PostgreSQL:** un servicio con dos bases lógicas: `auth_db` y `banco_db`.
- **Docker Swarm:** despliega los servicios con estado en el nodo etiquetado y permite replicar AUTH y BANCO.
- **Docker Compose:** cuatro contenedores; Nginx accesible por defecto en `localhost:8080`.
- **Nginx:** sirve el frontend; envía `/api/auth/` a AUTH y el resto de `/api/` a BANCO.
- **Alcance actual:** educativo, local, sin dominio público y sin dinero real.
- **Transferencia:** débito y crédito se escriben en la misma transacción de PostgreSQL.