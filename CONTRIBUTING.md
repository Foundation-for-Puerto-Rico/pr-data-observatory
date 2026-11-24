# Cómo contribuir

Estas reglas aplican a todas las personas con acceso al repo. Son pocas a propósito.

## Reglas

1. **Todo cambio a `main` entra por pull request.** Nadie hace push directo a `main`. GitHub lo bloquea con una regla del repo (ruleset), incluso para administradores.
2. **Trabaja en una rama propia.** Créala desde `main` actualizado y dale un nombre que diga qué hace, por ejemplo `data/gateway-traffic` o `fix/chat-years`.
3. **Puedes revisar y fusionar tu propio PR.** No hace falta la aprobación de otra persona. Revisa tú el diff completo en la pestaña **Files changed** antes de fusionar.
4. **Antes de fusionar, confirma que:**
   - La rama está al día con `main` y no tiene conflictos.
   - Las pruebas pasan. El workflow `tests.yml` las corre en cada PR (pruebas de Python y de Node, contrato de datos, español, archivos generados, peso de las páginas y privacidad). El ruleset de `main` exige el check `checks` antes de fusionar. En tu máquina: `python -m unittest discover -s tests` y `node --test tests/*.test.js`.
   - Si cambiaste datos, corriste el paso de `build.py` que los genera y los archivos de `site/data/` están en el PR.
   - La descripción del PR dice qué cambia y por qué, e incluye `Closes #N` por cada issue que resuelve (`Refs #N` si solo avanza).
5. **Pide revisión cuando el cambio lo amerite.** Es opcional, pero pídela si tocas el motor compartido (`site/js/core/`), el contrato de datos, licencias o fuentes, o algo que no estás seguro de cómo afecta al resto.
6. **Nunca reescribas la historia de `main`.** No se permite force-push ni borrar la rama.
7. **Cada palabra técnica nueva lleva su término en el glosario.** Si tu PR muestra una palabra técnica nueva en una página (etiqueta, leyenda, ayuda, ventana emergente, nombre de ficha), agrega el término a `dictionary_src/glossary.json` en el mismo PR, con definición en inglés y en español, una fuente con la fecha en que verificaste el enlace, sus formas de búsqueda y si se resalta. Luego corre `python dictionary.py`: el resaltador (`site/js/core/glossary.js`) subraya la palabra en todas las páginas y muestra su definición y su fuente, sin cambiar ninguna página. `python dictionary.py --check` falla si falta algo, y también si un término de prioridad 1 que aparece en la interfaz tiene `highlight: false` sin decir por qué en `highlight_why`; `tests/test_glossary.py` verifica lo mismo (`docs/glossary.md`).

## El job nocturno

La regla no tiene excepciones. El workflow nocturno `refresh-transit.yml` también pasa por un PR: cuando cambian los datos de transporte, abre la rama `bot/refresh-transit-<fecha>-<número de corrida>` y crea el PR como la GitHub App del observatorio (ver `docs/automation.md`). El PR corre `tests.yml` como cualquier otro y se fusiona solo cuando pasan las pruebas. Mientras la App no esté instalada, el job solo sube la rama y una persona abre el PR. Antes de publicar, `check_refresh.py` compara cada conteo con la copia publicada: si un archivo no se lee, queda vacío o baja más de una cuarta parte, el job se detiene y no publica nada. Si la baja es real (por ejemplo, venció el feed de un operador), una persona lo verifica y corre el workflow a mano con la opción **allow drop**.

## Publicación

Cada fusión a `main` que toca `site/` o `connector/` publica el sitio en Azure Static Web Apps (`pages.yml`; `docs/azure.md`). Para deshacer una publicación, abre un PR que revierta la fusión (`docs/workspace.md`, "From GitHub to production"). Si tu PR no debe salir todavía, déjalo abierto o márcalo como borrador (**Draft**).
