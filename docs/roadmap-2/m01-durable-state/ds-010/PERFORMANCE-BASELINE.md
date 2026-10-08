# Baseline de performance

Ambiente: Windows 11, Python 3.13.15, Redis 7.4.11 standalone, redis-py 6.4.0,
AOF ativo, `noeviction`, pool máximo 108 e 1.000 amostras por tamanho.

| Payload | Operação | Mediana | p95 |
| --- | --- | ---: | ---: |
| 1 KB | save / read / CAS / consume | 1,416 / 0,602 / 1,599 / 1,420 ms | 2,031 / 0,864 / 2,180 / 1,939 ms |
| 16 KB | save / read / CAS / consume | 1,544 / 0,698 / 1,790 / 1,522 ms | 2,106 / 0,949 / 2,382 / 1,988 ms |
| 256 KB | save / read / CAS / consume | 3,854 / 2,407 / 5,306 / 3,339 ms | 10,125 / 3,275 / 16,669 / 7,714 ms |

Throughput sequencial: 738,49; 671,64; e 219,14 operações/s. A carga com
100 workers realizou 2.971,12 operações/s em 0,101 s. Resultados locais são
baseline comparativa, não SLA nem limite oficial.
