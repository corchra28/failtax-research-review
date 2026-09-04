# Lista de ipoteze viitoare (FARA outcome-uri inspectate; doar structura observata)
1. Curatarea breadth-ului: 59 % din aparitiile cumparatorilor post-migrare provin din portofele prezente in > 5 pool-uri (max 817 pool-uri/portofel). O versiune a H1/H3 care exclude complet portofelele „pulverizatoare" (prior_mints_24h peste un prag distributional fixat pe DEV) ar testa daca cererea ramasa este informativa. Neevaluat.
2. Episoade la nivel de token pentru pool-urile secundare (SLOW_ATOMIC_REVERT_ARB V2): necesita metadatele mint (MINT_RPC_APPROVED) inainte de orice PnL.
3. Decizia la T0+60 s foloseste o singura fereastra; o analiza de supravietuire a cohortei incumbente (timp pana la epuizarea a 50 % din INVENTORY_PROXY) ca eveniment, nu ca prag, fara orizont ales din PnL.
4. Validarea taxelor cu tier demonstrat din evenimente pe intreaga banda (nu doar la intrare/iesire) si cuantificarea tranzactiilor cu taxa 0 pe tip de portofel.
Niciuna nu este autorizata pentru PnL; toate cer o preinregistrare separata si, ideal, o fereastra prospectiva noua.
