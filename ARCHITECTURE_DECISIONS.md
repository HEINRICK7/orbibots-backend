# Decisões de arquitetura do OrbiBots Backend

Este documento registra como o projeto aplica as skills `python-backend` e
`clean-arch-ddd-guard` sem modificar as skills originais. O arquivo [`spec.json`](spec.json)
parte do spec da skill de verificação e acrescenta metadados do projeto; o script
upstream ignora `project_conventions`.

## Conflitos e convenções adotadas

| Tema | `python-backend` | `clean-arch-ddd-guard` | Convenção deste projeto |
| --- | --- | --- | --- |
| Controllers HTTP | Trata controllers HTTP como entrypoints em `infra/entrypoints`. | Define `infra/controllers` para controllers REST. | Rotas e adaptação HTTP ficam em `infra/controllers`; criação da aplicação e ciclo de vida ficam em `infra/entrypoints`. |
| Contratos e adaptadores de gateway | Coloca portas de aplicação em `application` e implementações concretas de persistência em `infra`. | O guia de pastas sugere gateways em `application/gateways`; o checklist também pede que cada implementação declare o contrato implementado. | Portas que pertencem ao domínio ficam em `domain/interfaces`; portas de aplicação, como transações, ficam em `application/gateways`; implementações SQLAlchemy ficam em `infra/adapters` e declaram explicitamente seus Protocols. |
| Protocols de casos de uso | Favorece contratos próximos aos casos de uso da aplicação. | Coloca contratos de use case em `domain/interfaces/usecases`. | Mantemos os Protocols existentes em `domain/interfaces/usecases` para evitar uma mudança ampla de API interna; novas dependências de aplicação ficam em `application/gateways` quando não são conceitos de domínio. |
| Composição e inicialização | Define `infra/di` como composition root e recomenda manter setup técnico separado. | Reserva `infra/di` para composição e `infra/setup` para bootstrap/configuração. | `infra/di` constrói adapters e casos de uso; setup mantém leitura de ambiente, ciclo de sessão e entrada CLI. O caso de uso de provisionamento controla a transação por uma porta `UnitOfWork`. |
| Diretórios obrigatórios vazios | A regra de simplicidade recomenda não manter diretórios vazios sem responsabilidade. | O spec upstream exige `application/configuration`, `application/gateways` e `domain/config`. | Os três continuam obrigatórios no spec. `application/gateways` agora contém a porta de transação; `application/configuration` e `domain/config` seguem vazios e são mantidos até uma decisão separada sobre o spec/checker. |

## Limites de dependência

- `domain` não importa frameworks nem camadas externas.
- `application` depende de contratos, DTOs e regras internas; não importa SQLAlchemy,
  FastAPI ou bibliotecas de infraestrutura.
- `infra` implementa Protocols e compõe os casos de uso concretos.
- `InitialAdminProvisioner` mantém a sessão CLI; `ProvisionInitialAdminsUseCase`
  implementa o contrato `ProvisionInitialAdmins`, coordena a validação e
  provisionamento e controla commit/rollback via `UnitOfWork`. O DTO de entrada é
  compartilhado com o entrypoint CLI e não expõe a senha na representação (`repr`).
- A decisão de elegibilidade para conceder ADMIN está em
  `GrantGlobalAdminUseCase`; o repositório apenas consulta o candidato e persiste a
  alteração.
- O exception handler devolve apenas detalhes públicos definidos em código, nunca
  `str(exc)`.
- `logging.conf` é carregado no bootstrap; `LOG_LEVEL` pode ajustar o nível do root e
  dos handlers, com `INFO` como padrão.

## Verificação

O spec conserva a lista original de diretórios obrigatórios e adapta apenas metadados
descritivos do projeto. Execute o guard com:

```bash
python /home/carlos-henrique/.codex/skills/clean-arch-ddd-guard/scripts/check_structure.py app --spec spec.json
```

O resultado do checker não substitui a inspeção de conteúdo e dependências; ele valida
somente as regras implementadas pelo script upstream.
