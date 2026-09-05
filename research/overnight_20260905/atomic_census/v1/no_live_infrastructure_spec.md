# Specificatie minimala de implementare FARA LIVE (ce ar fi necesar DACA slow-capture ar fi trecut; nu a trecut)
- Sursa de stare: WSS logsSubscribe pe PumpSwap (ca in colectorul existent) + decodare Buy/Sell/CreatePool; in plus Deposit/Withdraw (nedecodate acum) pentru consistenta lantului fara ancore.
- Metadate: harta pool -> (index, creator, base, quote) din getMultipleAccounts (deja recuperata o data) + owner-ul mint-ului (SPL Token vs Token-2022) — obligatoriu inainte de orice ruta.
- Decizie: stare completa la finalul slotului s; toate rutele ordonate; ruta cu predicted maxim; un candidat per episod de dislocare la nivel de token; max o tranzactie per slot.
- Tranzactie: o singura tranzactie cu doua instructiuni PumpSwap (buy exact base_out B cu max_quote_in; sell exact base_in B cu min_quote_out = max_quote_in + cost); fara router; revert atomic la esec.
- Landing asumat +3 sloturi (obisnuit), stres +5; fara Jito.
- Capital: 0,25 SOL per tranzactie + rezerva pentru taxe de revert (0,000105 SOL per esec); ATA recuperabil.
- Interzis: orice executie inainte de un forward test paper separat aprobat; nu exista candidat in prezent.
