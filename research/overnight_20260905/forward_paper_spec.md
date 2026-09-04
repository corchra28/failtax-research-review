# Specificatie minimala de paper-trading prospectiv (NU se porneste; necesita aprobare separata si un colector nou)
- Populatie: migrari BOOST canonice, CompleteEvent + CreatePoolEvent observate live; decizie T0+60 s; intrare la prima stare completa dupa decizie; 0,25 SOL; iesire +60 s; jurnal cu ts de decizie, hash-ul regulii inghetate si semnalul calculat INAINTE de intrare.
- Regula: doar o ipoteza preinregistrata (niciuna nu a trecut poarta overnight ⇒ nu exista candidat de trimis in forward test).
- Masurare: shadow fara ordine reale; comparatie cu placebo si complement; oprire automata la 500 semnale sau 14 zile; fara modificari in timpul ferestrei.
- Conditii: colector WSS dedicat (aprobare), cheie fara drepturi de semnare, fara portofel.
