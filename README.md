# Az "Okos" Bollinger-szalag: Kalman-szűrő alapú dinamikus sávok

Az „okos” Bollinger-szalag a hagyományos, statikus statisztikán alapuló indikátorok modern, adaptív alternatívája. Míg a klasszikus Bollinger-szalag rögzített időablakot használ, ez a módszer a **Kalman-szűrőt** és a **Maximális Valószínűségű Becslést (MLE)** ötvözi.

## 1. Alapvető elv: MLE a háttérben

A módszer alapja a **Maximum Likelihood (MLE)** elve, amely szerint a modell paramétereit úgy választjuk meg, hogy a megfigyelt adatok a lehető legvalószínűbbek legyenek. A Kalman-szűrő ezt a becslést rekurzívan, minden új adatpontnál elvégzi.

* **Középvonal ($\hat{x}_t$):** A szűrő által becsült aktuális állapot, amely megfelel a legvalószínűbb értéknek az eddigi adatok alapján.
* **Bizonytalanság ($P_t$):** A hiba-kovariancia, amely megmutatja, mekkora a becslés szórása a modell szerint.

## 2. Matematikai felépítés

A sávokat a szűrő belső bizonytalansági mutatója határozza meg:

$$Sávok = \hat{x}_t \pm k \cdot \sqrt{P_t}$$

Ahol:
* $\hat{x}_t$: A Kalman-szűrő aktuális tippje az árfolyamra/hozamra.
* $P_t$: A becsült hiba varianciája.
* $k$: Kockázati szorzó (általában 2).

Mivel az MLE variancia-becslése ($1/n$-nel osztva) hajlamos lehet a torzításra, a Kalman-szűrő ezt a folyamatzaj ($Q$) és a mérési zaj ($R$) mátrixok dinamikus hangolásával korrigálja.

---

## 3. Összehasonlítás: Hagyományos vs. "Okos" sávok

| Jellemző | Hagyományos Bollinger-szalag | „Okos” (Kalman-alapú) sáv |
| :--- | :--- | :--- |
| **Számítás módja** | Mozgóátlag és szórás (SMA/StdDev). | Rekurzív állapotbecslés (MLE logika). |
| **Reakcióidő** | Lassú, fáziskéséssel követi a trendet. | Adaptív, azonnal reagál a piaci változásokra. |
| **Zajkezelés** | Minden adatot egyformán súlyoz az ablakban. | A likelihood alapján súlyozza az új információt. |
| **Sávszélesség** | Fix 20 napos volatilitást néz. | A modell aktuális bizonytalanságát ($P_t$) követi. |

---

## 4. Előnyök a pénzügyi modellezésben

1.  **Dinamikus Stop-Loss:** A sávok távolsága nem fix, hanem a piaci zaj függvényében tágul vagy szűkül. Ez segít elkerülni, hogy egy átmeneti tüske kiüsse a pozíciót.
2.  **MSE Minimalizálás:** A Kalman-szűrő célja a várható négyzetes hiba minimalizálása, ami matematikailag megegyezik a normális zajfeltételezés melletti MLE-vel.
3.  **Trendfordulók felismerése:** Ha az árfolyam tartósan elhagyja a sávot, a modell log-likelihoodja csökken, ami jelzi a korábbi modell érvénytelenségét.

## 5. Implementációs megjegyzés
A gépi tanulásban használt legtöbb veszteségfüggvény (pl. MSE vagy Cross-entropy) valójában az MLE-ből származtatható. Az „okos” sávok használata gyakorlatilag egy folyamatosan tanuló, mini AI-t helyez el a grafikonon.