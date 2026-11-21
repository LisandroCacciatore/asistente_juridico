# Fase B — Épicas en Gherkin

Especificación de trabajo. Una épica por vez, una rama y un PR por épica,
pruebas primero. Nada toca SISFE real hasta la ventana de prueba con Santiago y Jr.

## Reglas para el agente

- No empezar la épica N+1 sin pruebas en verde y revisión de la N.
- Ningún escenario firma ni presenta en SISFE real: todo con doble de prueba,
  salvo la ventana acordada.
- Un trabajo en estado dudoso nunca se reintenta solo: se marca y lo resuelve
  una persona.
- El portal no navega SISFE ni firma. Firmar y presentar viven en el asistente,
  en la máquina del estudio.
- Cada épica deja constancia en `docs/FASE-B-BRECHA.md` y en la auditoría.

---

## Épica 0 · Decisiones previas

```gherkin
# language: es
Característica: Decisiones que cierra Santiago antes de construir

  Escenario: Dónde está el token de cada firmante
    Dado que Jr y el Socio firman con su propio token o 2FA
    Cuando se pide firmar desde el portal
    Entonces debe estar definido dónde está físicamente cada token
    Y debe estar definido quién está frente a la máquina del estudio cuando aparece la pausa
    # Bloquea la épica 4. Si el token no está en la máquina del estudio, la firma remota cambia de diseño.

  Escenario: Quién puede pedir firmar y presentar
    Dado que Santiago decidió que cada uno actúa por sí mismo y no hay delegaciones
    Cuando alguien pide firmar o presentar
    Entonces solo puede pedirlo el dueño de la cédula
    Y el administrador no puede pedir en nombre de otro
    # Ya decidido: registrarlo en docs/FASE-B-BRECHA.md.

  Escenario: Dónde vive el portal
    Dado que el asistente debe quedarse en la máquina del estudio
    Cuando se decide dónde corre el portal
    Entonces el portal corre en la máquina del estudio, expuesto con Tailscale
    Y la opción de un VPS con el asistente queda descartada

  Escenario: Qué pasa si un trabajo se traba
    Cuando un trabajo supera su tiempo límite
    Entonces queda visible en el panel con su estado
    Y se define si además se avisa por correo
```

---

## Épica 1 · Autenticación del asistente local

Prioridad cero. Es independiente de la Fase B: hoy `servidor.py` escucha en
`127.0.0.1:8000` sin validar nada, y un sitio abierto en el navegador de Santiago
también puede mandarle pedidos a localhost.

```gherkin
# language: es
Característica: Solo el portal puede dar órdenes al asistente

  Escenario: Pedido sin credencial
    Dado que el asistente está corriendo
    Cuando llega un pedido de acción sin token compartido
    Entonces responde 401
    Y no ejecuta nada
    Y lo anota en el registro

  Escenario: Pedido con token correcto
    Cuando llega un pedido con el token compartido válido
    Entonces lo acepta para validación posterior

  Escenario: Pedido desde una página web ajena
    Dado que el navegador de Santiago abre un sitio cualquiera
    Cuando ese sitio intenta enviar un pedido a 127.0.0.1:8000
    Entonces el asistente lo rechaza por Origin o Host no permitido

  Escenario: Secreto compartido fuera del repositorio
    Entonces el token vive en config.py, que está en .gitignore
    Y no aparece en logs ni en mensajes de error
```

---

## Épica 2 · Lista cerrada de acciones

```gherkin
# language: es
Característica: El asistente solo acepta firmar y presentar

  Escenario Esquema del escenario: Acción fuera de la lista
    Cuando llega un pedido con la acción "<accion>"
    Entonces lo rechaza con un error claro
    Y no ejecuta nada

    Ejemplos:
      | accion            |
      | ejecutar_comando  |
      | borrar_cedula     |
      | acción vacía      |

  Escenario: Acciones permitidas
    Cuando llega un pedido con la acción "firmar_lote" o "presentar"
    Entonces lo pasa a la verificación de identidad
```

---

## Épica 3 · Cola persistente y estados

Hoy `JOBS` es un diccionario en memoria. Si el asistente reinicia, se pierden el
trabajo y la pausa.

```gherkin
# language: es
Característica: Trabajos que sobreviven a un reinicio

  Escenario: Ciclo normal de un pedido
    Cuando se crea un pedido válido
    Entonces pasa por pedido, en_cola, corriendo, esperando_humano y listo
    Y cada cambio queda guardado en disco

  Escenario: Reinicio con un trabajo en cola
    Dado un trabajo en estado en_cola
    Cuando el asistente se reinicia
    Entonces el trabajo sigue en cola y se ejecuta

  Escenario: Reinicio con un trabajo corriendo
    Dado un trabajo en estado corriendo o esperando_humano
    Cuando el asistente se reinicia
    Entonces el trabajo pasa a estado dudoso
    Y no se reintenta solo
    Y una persona decide si reintentar, después de revisar SISFE

  Escenario: Tiempo límite
    Dado un trabajo que supera su tiempo límite
    Entonces pasa a error con el motivo
    Y queda visible para su dueño
```

---

## Épica 4 · Identidad, perfil y firma con pausa local

```gherkin
# language: es
Característica: El asistente decide quién es quién

  Escenario: El portal dice "soy Jr"
    Cuando llega un pedido que declara la identidad "jr"
    Entonces el asistente la resuelve contra config.PERSONAS
    Y toma el perfil de Chrome de Jr
    Y aplica verificar_cadena antes de tocar nada

  Escenario: Identidad que no coincide
    Dado un pedido de Jr sobre una cédula de Santiago
    Entonces lo rechaza
    Y no usa el perfil de Santiago
    # Test obligatorio: un pedido de Jr nunca corre con la identidad de Santiago.

  Escenario: Pausa de FirmAr
    Cuando el trabajo llega al paso del token
    Entonces pasa a esperando_humano
    Y la confirmación se hace solo en la máquina del estudio
    Y un clic remoto no puede firmar

  Escenario: Sin token no hay firma
    Dado un pedido legítimo del dueño de la cédula
    Cuando el firmante no pone el token
    Entonces el trabajo expira en error
    Y no se firma nada

  Escenario: Un perfil de Chrome a la vez
    Dado dos trabajos de la misma persona
    Entonces se encolan y corren de a uno
    Y dos personas distintas corren en paralelo solo si los perfiles lo permiten
```

---

## Épica 5 · Pausa dirigida al firmante

```gherkin
# language: es
Característica: La pausa le llega a quien pidió el trabajo

  Escenario: Aviso al firmante
    Cuando un trabajo entra en esperando_humano
    Entonces el aviso le llega a la persona que lo pidió

  Escenario: Quién destraba
    Dado un trabajo esperando_humano de Jr
    Cuando otra persona llama a /api/continuar
    Entonces el asistente lo rechaza
```

---

## Épica 6 · Presentar con idempotencia

Presentar en SISFE no se deshace. Esta épica es la más delicada.

```gherkin
# language: es
Característica: Una cédula se presenta una sola vez

  Escenario: Dos clics sobre la misma cédula
    Dado dos pedidos de presentar sobre la misma cédula
    Entonces se crea una sola presentación
    Y el segundo pedido recibe un aviso claro
    # Bloqueo por cédula, no por pedido.

  Escenario: Solo cédulas firmadas
    Dado una cédula sin ruta_firmada
    Cuando se pide presentarla
    Entonces lo rechaza

  Escenario: Confirmación humana final
    Cuando el trabajo está por presentar
    Entonces exige una confirmación en la máquina del estudio
    Y no existe opción para saltearla

  Escenario: SISFE no responde
    Cuando SISFE falla a mitad de la presentación
    Entonces el trabajo queda en estado dudoso
    Y nunca se reintenta automáticamente
    Y antes de reintentar una persona verifica en SISFE si la presentación ya entró

  Escenario: Modo de ensayo
    Dado el modo de ensayo activado
    Entonces recorre todo el flujo hasta la confirmación final sin presentar nada
```

---

## Épica 7 · Auditoría unificada

```gherkin
# language: es
Característica: Un solo registro, cruzado por id de trabajo

  Escenario: Pedido y ejecución
    Cuando se pide y se ejecuta un trabajo
    Entonces el portal anota quién lo pidió, cuándo y con qué identidad
    Y el asistente anota la ejecución y el resultado
    Y ambos registros se cruzan por el id del trabajo

  Escenario: Rechazos
    Cuando se rechaza un pedido por token, identidad o acción no permitida
    Entonces también queda en la auditoría con el motivo
```

---

## Épica 8 · Interfaz en el portal

Va al final. Sin las capas anteriores, el botón es un peligro.

```gherkin
# language: es
Característica: Pedir y seguir un trabajo desde el portal

  Escenario: Botón visible solo al dueño
    Dado una cédula firmada o generada del usuario actual
    Entonces ve los botones Firmar o Presentar según el estado
    Y no los ve en cédulas ajenas

  Escenario: El administrador no pide por otros
    Dado que Santiago entra como administrador a una cédula de Jr
    Entonces la ve pero no puede pedir firmar ni presentar

  Escenario: Estado visible
    Cuando hay un trabajo en curso
    Entonces el panel muestra su estado y el motivo si hubo error

  Escenario: Mensajes en lenguaje de usuario
    Cuando algo falla
    Entonces el mensaje dice qué pasó y qué hacer, sin términos técnicos
```

---

## Épica 9 · Canal portal-asistente (solo si hace falta)

```gherkin
# language: es
Característica: Comunicación entre portal y asistente

  Escenario: Ambos en la misma máquina
    Dado el portal y el asistente en la máquina del estudio
    Entonces comparten la cola local y no hace falta ningún canal de red

  Escenario: Portal fuera de la máquina del estudio
    Dado que el portal se muda a otro servidor
    Entonces el asistente consulta al portal cada N segundos, solo con conexiones salientes
    Y no abre puertos ni necesita IP pública
```

---

## Prueba final con tokens reales

```gherkin
# language: es
Característica: Ventana de prueba con Santiago y Jr

  Escenario: Firma real con cédula de prueba
    Dado una ventana acordada con Santiago y Jr
    Y una cédula de prueba que no se presenta
    Cuando piden firmar desde el portal y ponen el token
    Entonces la cédula queda firmada con la identidad correcta
    Y la auditoría muestra el recorrido completo
```
