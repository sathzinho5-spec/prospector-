# proposito: porta de entrada da analise; reexporta pra nenhuma chamada de fora mudar
#
# O conteudo saiu para tres arquivos por responsabilidade. Este reexporta a
# interface publica inteira, entao quem chama segue fazendo analyzer.build_report,
# analyzer.business_strategy, analyzer.pitch_message sem uma linha mudada.
from analysis.copy_comercial import (PROPOSAL_PROMPT, STRATEGY_PROMPT, _local_proposal,
                                     _local_strategy, business_strategy, proposal)
from analysis.copy_fechamento import (OBJECTION_PROMPT, PITCH_PROMPT, TONS, _local_objection,
                                      _local_pitch, _montar_prompt, handle_objection,
                                      pitch_message)
from analysis.instagram_report import (NEGATIVE, POSITIVE, _build_metrics, _detect_tone,
                                       _strong_points, _top_hashtags, ai_analysis,
                                       build_report, local_analysis)
