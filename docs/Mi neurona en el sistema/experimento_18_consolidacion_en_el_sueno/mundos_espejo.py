"""Experimento 18, E0 — corpus espejo escrito a mano (PROTOCOLO.md §4).

8 temas × 3 recuerdos, el MISMO contenido en español, inglés, chino y japonés.
Los tres recuerdos de un tema tratan facetas distintas y comparten pocas palabras, a propósito,
para evitar la filtración léxica del experimento 16 (pseudopalabras exclusivas por tema).

Puentes (rasgo compartido entre temas distintos, «rojo»): los 3 pares entre
(cocina, 1), (bomberos, 0) y (jardin, 0). Se reportan aparte; no son positivos ni negativos.

I: 8 recuerdos irrelevantes (finanzas, trámites, música) para la prueba de invariancia.
No toca el motor ni ninguna base de datos.
"""

TEMAS = ["cocina", "bomberos", "astronomia", "jardin", "basedatos", "futbol", "medicina", "tren"]

# D[idioma] = lista de 24 textos en orden tema-major: índice = tema*3 + faceta
D = {
    "es": [
        "Para la salsa, sofreír ajo y cebolla en aceite de oliva y añadir tomates maduros triturados; cocinar a fuego lento veinte minutos.",
        "La pasta queda mejor si se escurre al dente y se mezcla en la sartén con la salsa roja, guardando un poco del caldo de la cocción.",
        "Una pizza casera necesita masa reposada dos horas, una capa fina de tomate, mozzarella fresca y el horno muy caliente.",
        "El camión de bomberos, pintado de rojo, salió de la estación a las tres de la madrugada con la sirena encendida.",
        "Los bomberos usaron la escalera telescópica para rescatar a una familia atrapada en el cuarto piso del edificio.",
        "Tras apagar el incendio, los peritos revisaron el cableado y concluyeron que un cortocircuito originó las llamas.",
        "Durante el eclipse total de sol, la luna cubrió el disco solar y el cielo se oscureció casi cuatro minutos.",
        "Con el telescopio nuevo pudimos ver los anillos de Saturno y cuatro lunas de Júpiter desde la azotea.",
        "Las estrellas fugaces de las Perseidas se ven mejor en agosto, lejos de las luces de la ciudad.",
        "Las rosas rojas necesitan poda a finales del invierno y abono rico en potasio para florecer en primavera.",
        "Regar el huerto temprano por la mañana evita que el sol evapore el agua antes de que llegue a las raíces.",
        "Los pulgones atacaron los tallos jóvenes; los quitamos con agua jabonosa y soltamos mariquitas en el jardín.",
        "La consulta tardaba diez segundos hasta que añadimos un índice sobre la columna de fecha en la tabla de pedidos.",
        "Antes de migrar el esquema hicimos una copia de seguridad completa y probamos la restauración en otro servidor.",
        "El error de concurrencia aparecía cuando dos procesos escribían a la vez; lo resolvimos con transacciones y bloqueos.",
        "El partido terminó dos a uno con un gol de cabeza en el último minuto del tiempo de descuento.",
        "El entrenador cambió a una defensa de cinco y las figuras del equipo apenas tocaron el balón.",
        "Los aficionados llenaron el estadio cantando himnos desde dos horas antes del pitido inicial.",
        "La enfermera aplicó la segunda dosis de la vacuna y pidió esperar quince minutos por si aparecía alguna reacción.",
        "El médico recetó antibióticos durante siete días y recomendó volver si la fiebre no bajaba en tres.",
        "Los análisis de sangre mostraron el colesterol alto, así que el cardiólogo sugirió cambiar la dieta y caminar.",
        "El tren subió entre montañas nevadas y cruzó un viaducto de piedra sobre un río verde.",
        "Compramos los billetes con un mes de antelación y conseguimos asientos junto a la ventana en el vagón panorámico.",
        "Al llegar al pueblo de la cordillera dormimos en un refugio y al amanecer hicimos una ruta hasta el lago glaciar.",
    ],
    "en": [
        "For the sauce, fry garlic and onion in olive oil and add crushed ripe tomatoes; simmer on low heat for twenty minutes.",
        "Pasta is better drained al dente and tossed in the pan with the red sauce, keeping a little of the cooking liquid.",
        "A homemade pizza needs dough rested for two hours, a thin layer of tomato, fresh mozzarella and a very hot oven.",
        "The fire truck, painted red, left the station at three in the morning with its siren on.",
        "The firefighters used the telescopic ladder to rescue a family trapped on the fourth floor of the building.",
        "After putting out the fire, the inspectors checked the wiring and concluded that a short circuit started the flames.",
        "During the total solar eclipse, the moon covered the solar disk and the sky went dark for almost four minutes.",
        "With the new telescope we could see the rings of Saturn and four moons of Jupiter from the rooftop.",
        "The Perseid shooting stars are best seen in August, far from the city lights.",
        "Red roses need pruning at the end of winter and a potassium-rich fertilizer to bloom in spring.",
        "Watering the vegetable garden early in the morning keeps the sun from evaporating the water before it reaches the roots.",
        "Aphids attacked the young stems; we removed them with soapy water and released ladybugs in the garden.",
        "The query took ten seconds until we added an index on the date column of the orders table.",
        "Before migrating the schema we made a full backup and tested the restore on another server.",
        "The concurrency bug appeared when two processes wrote at the same time; we solved it with transactions and locks.",
        "The match ended two to one with a header in the last minute of stoppage time.",
        "The coach switched to a five-man defense and the team's best players barely touched the ball.",
        "The fans filled the stadium singing anthems two hours before kickoff.",
        "The nurse gave the second dose of the vaccine and asked us to wait fifteen minutes in case of any reaction.",
        "The doctor prescribed antibiotics for seven days and advised coming back if the fever did not drop within three.",
        "The blood tests showed high cholesterol, so the cardiologist suggested changing the diet and walking.",
        "The train climbed between snowy mountains and crossed a stone viaduct over a green river.",
        "We bought the tickets a month in advance and got window seats in the panoramic carriage.",
        "When we reached the mountain village we slept in a hut and at dawn hiked to the glacier lake.",
    ],
    "zh": [
        "做酱汁时，先用橄榄油炒蒜和洋葱，再加入压碎的熟番茄，小火慢炖二十分钟。",
        "意大利面煮到有嚼劲时捞出，放进锅里和红色酱汁拌匀，留一点煮面汤。",
        "自制披萨需要醒面两个小时，铺一层薄薄的番茄，放新鲜马苏里拉奶酪，用很热的烤箱。",
        "那辆漆成红色的消防车凌晨三点鸣着警笛驶出了消防站。",
        "消防员用伸缩云梯救出了被困在大楼四层的一家人。",
        "火被扑灭后，鉴定人员检查了电线，认定是短路引起了火焰。",
        "日全食期间，月亮遮住了太阳圆盘，天空暗了将近四分钟。",
        "用新的望远镜，我们在屋顶上看到了土星的光环和木星的四颗卫星。",
        "英仙座流星雨在八月最容易看到，要远离城市的灯光。",
        "红玫瑰需要在冬末修剪，并施富含钾的肥料，才能在春天开花。",
        "清晨给菜园浇水，可以避免太阳在水渗到根部之前就把它蒸发掉。",
        "蚜虫啃食了嫩茎；我们用肥皂水把它们清除，又在花园里放了瓢虫。",
        "这个查询要花十秒钟，直到我们在订单表的日期列上加了索引。",
        "迁移数据库结构之前，我们做了完整备份，并在另一台服务器上测试了恢复。",
        "并发错误出现在两个进程同时写入的时候；我们用事务和锁解决了它。",
        "比赛在补时最后一分钟靠一个头球以二比一结束。",
        "教练改打五后卫，球队的核心球员几乎碰不到球。",
        "球迷们在开球前两个小时就唱着队歌坐满了体育场。",
        "护士打了第二针疫苗，让我们等十五分钟，以防出现不良反应。",
        "医生开了七天的抗生素，并建议如果三天内不退烧就再来复诊。",
        "验血结果显示胆固醇偏高，所以心脏科医生建议调整饮食并多走路。",
        "火车在雪山之间爬升，穿过一座横跨绿色河流的石头高架桥。",
        "我们提前一个月买了车票，在全景车厢里拿到了靠窗的座位。",
        "到了山区的村子后，我们在小屋里过夜，黎明时徒步去了冰川湖。",
    ],
    "ja": [
        "ソースを作るときは、オリーブオイルでにんにくと玉ねぎを炒め、つぶした完熟トマトを加えて弱火で二十分煮込む。",
        "パスタはアルデンテで湯を切り、フライパンで赤いソースと和えて、ゆで汁を少し残しておくとおいしい。",
        "手作りピザには二時間寝かせた生地、薄く塗ったトマト、新鮮なモッツァレラ、そしてとても熱いオーブンが必要だ。",
        "赤く塗られた消防車が、サイレンを鳴らしながら午前三時に消防署を出発した。",
        "消防士たちははしご車を使って、建物の四階に閉じ込められた家族を救出した。",
        "火事が消し止められた後、調査員が配線を調べ、ショートが炎の原因だと結論づけた。",
        "皆既日食の間、月が太陽の円盤を覆い、空はほぼ四分間暗くなった。",
        "新しい望遠鏡で、屋上から土星の環と木星の四つの衛星を見ることができた。",
        "ペルセウス座流星群は八月に、街の明かりから離れた場所で見るのがいちばんだ。",
        "赤いバラは冬の終わりに剪定し、春に咲かせるためにカリウムの多い肥料を与える必要がある。",
        "家庭菜園に朝早く水をやると、根に届く前に日差しで水が蒸発するのを防げる。",
        "アブラムシが若い茎を襲ったので、石けん水で取り除き、庭にテントウムシを放した。",
        "注文テーブルの日付の列にインデックスを追加するまで、そのクエリは十秒かかっていた。",
        "スキーマを移行する前に完全なバックアップを取り、別のサーバーで復元を試した。",
        "二つのプロセスが同時に書き込むと並行処理のバグが出たが、トランザクションとロックで解決した。",
        "試合はアディショナルタイム最後の一分のヘディングゴールで二対一で終わった。",
        "監督は五バックに変更し、チームの中心選手たちはほとんどボールに触れなかった。",
        "サポーターたちはキックオフの二時間前から応援歌を歌い、スタジアムを埋め尽くした。",
        "看護師はワクチンの二回目を接種し、何か反応が出ないか十五分待つように言った。",
        "医者は抗生物質を七日分処方し、三日たっても熱が下がらなければまた来るように勧めた。",
        "血液検査でコレステロールが高いとわかり、循環器内科の医師は食事を変えて歩くことを勧めた。",
        "列車は雪をかぶった山々の間を登り、緑の川にかかる石の高架橋を渡った。",
        "一か月前に切符を買って、展望車両の窓側の席を取ることができた。",
        "山あいの村に着くと山小屋に泊まり、夜明けに氷河湖までハイキングした。",
    ],
}

I = {
    "es": [
        "La hipoteca a tipo fijo protege de las subidas del interés, aunque la cuota inicial sea algo más alta.",
        "El contrato de alquiler incluye una cláusula de renovación automática salvo aviso con dos meses.",
        "La orquesta ensayó la sinfonía de Brahms con un nuevo director invitado.",
        "Declaramos los impuestos en abril y recibimos la devolución a las seis semanas.",
        "El violinista afinó su instrumento antes del concierto de cámara.",
        "El banco cobra una comisión por transferencias internacionales superiores a mil euros.",
        "La notaria leyó la escritura completa antes de que los compradores firmaran.",
        "El coro infantil cantó villancicos en la plaza del ayuntamiento.",
    ],
    "en": [
        "A fixed-rate mortgage protects against interest rate rises, even if the initial payment is somewhat higher.",
        "The rental contract includes an automatic renewal clause unless notice is given two months ahead.",
        "The orchestra rehearsed the Brahms symphony with a new guest conductor.",
        "We filed our taxes in April and received the refund six weeks later.",
        "The violinist tuned his instrument before the chamber concert.",
        "The bank charges a fee for international transfers above one thousand euros.",
        "The notary read the whole deed before the buyers signed.",
        "The children's choir sang carols in the town hall square.",
    ],
    "zh": [
        "固定利率房贷能防止利率上涨，即使初期月供稍高一些。",
        "租房合同包含自动续约条款，除非提前两个月通知。",
        "管弦乐团和一位新的客座指挥排练了勃拉姆斯的交响曲。",
        "我们四月报了税，六周后收到了退税。",
        "小提琴手在室内音乐会前给他的乐器调了音。",
        "银行对超过一千欧元的国际转账收取手续费。",
        "公证员在买方签字前宣读了整份契据。",
        "儿童合唱团在市政厅广场唱了圣诞颂歌。",
    ],
    "ja": [
        "固定金利の住宅ローンは金利の上昇から守ってくれるが、最初の返済額は少し高くなる。",
        "賃貸契約には、二か月前に通知しない限り自動更新される条項がある。",
        "オーケストラは新しい客演指揮者とブラームスの交響曲をリハーサルした。",
        "四月に税金を申告し、六週間後に還付金を受け取った。",
        "バイオリニストは室内楽コンサートの前に楽器を調律した。",
        "銀行は千ユーロを超える国際送金に手数料を取る。",
        "公証人は買い手が署名する前に証書を全部読み上げた。",
        "子どもの合唱団が市役所前の広場でクリスマスキャロルを歌った。",
    ],
}

PUENTES = {frozenset((0 * 3 + 1, 1 * 3 + 0)), frozenset((0 * 3 + 1, 3 * 3 + 0)), frozenset((1 * 3 + 0, 3 * 3 + 0))}


def etiqueta(i, j):
    """'pos' (mismo tema) · 'puente' · 'neg'."""
    if i // 3 == j // 3:
        return "pos"
    if frozenset((i, j)) in PUENTES:
        return "puente"
    return "neg"


assert all(len(v) == 24 for v in D.values()) and all(len(v) == 8 for v in I.values())
