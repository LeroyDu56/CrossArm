/PROG  POINTDIRECT
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "PointDirect";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 308;
MEMORY_SIZE	= 0;
PROTECT		= READ_WRITE;
TCD:  STACK_SIZE	= 0,
      TASK_PRIORITY	= 50,
      TIME_SLICE	= 0,
      BUSY_LAMP_OFF	= 0,
      ABORT_REQUEST	= 0,
      PAUSE_REQUEST	= 0;
DEFAULT_GROUP	= 1,*,*,*,*;
CONTROL_CODE	= 00000000 00000000;
/MN
   1:  !RAPID PointProbe.PointDirect ;
   2:  UFRAME_NUM=1 ;
   3:  UTOOL_NUM=1 ;
   4:J P[1] 22% FINE    ;
   5:  UFRAME_NUM=0 ;
   6:  UTOOL_NUM=9 ;
   7:  PR[R[90]]=LPOS    ;
   8:  R[90]=R[90]+1    ;
   9:  UFRAME_NUM=1 ;
  10:  UTOOL_NUM=1 ;
  11:L P[2] 200mm/sec FINE    ;
  12:  UFRAME_NUM=0 ;
  13:  UTOOL_NUM=9 ;
  14:  PR[R[90]]=LPOS    ;
  15:  R[90]=R[90]+1    ;
  16:  UFRAME_NUM=1 ;
  17:  UTOOL_NUM=1 ;
  18:L P[3] 1000mm/sec FINE    ;
  19:  UFRAME_NUM=0 ;
  20:  UTOOL_NUM=9 ;
  21:  PR[R[90]]=LPOS    ;
  22:  R[90]=R[90]+1    ;
  23:  UFRAME_NUM=1 ;
  24:  UTOOL_NUM=1 ;
  25:J P[4] 22% FINE    ;
  26:  UFRAME_NUM=0 ;
  27:  UTOOL_NUM=9 ;
  28:  PR[R[90]]=LPOS    ;
  29:  R[90]=R[90]+1    ;
  30:  UFRAME_NUM=1 ;
  31:  UTOOL_NUM=1 ;
  32:L P[5] 200mm/sec FINE    ;
  33:  UFRAME_NUM=0 ;
  34:  UTOOL_NUM=9 ;
  35:  PR[R[90]]=LPOS    ;
  36:  R[90]=R[90]+1    ;
  37:  UFRAME_NUM=1 ;
  38:  UTOOL_NUM=1 ;
  39:L P[6] 1000mm/sec FINE    ;
  40:  UFRAME_NUM=0 ;
  41:  UTOOL_NUM=9 ;
  42:  PR[R[90]]=LPOS    ;
  43:  R[90]=R[90]+1    ;
  44:  UFRAME_NUM=1 ;
  45:  UTOOL_NUM=1 ;
  46:J P[7] 22% FINE    ;
  47:  UFRAME_NUM=0 ;
  48:  UTOOL_NUM=9 ;
  49:  PR[R[90]]=LPOS    ;
  50:  R[90]=R[90]+1    ;
  51:  UFRAME_NUM=1 ;
  52:  UTOOL_NUM=1 ;
  53:L P[8] 200mm/sec FINE    ;
  54:  UFRAME_NUM=0 ;
  55:  UTOOL_NUM=9 ;
  56:  PR[R[90]]=LPOS    ;
  57:  R[90]=R[90]+1    ;
  58:  UFRAME_NUM=1 ;
  59:  UTOOL_NUM=1 ;
  60:L P[9] 1000mm/sec FINE    ;
  61:  UFRAME_NUM=0 ;
  62:  UTOOL_NUM=9 ;
  63:  PR[R[90]]=LPOS    ;
  64:  R[90]=R[90]+1    ;
  65:  UFRAME_NUM=1 ;
  66:  UTOOL_NUM=1 ;
  67:J P[10] 22% FINE    ;
  68:  UFRAME_NUM=0 ;
  69:  UTOOL_NUM=9 ;
  70:  PR[R[90]]=LPOS    ;
  71:  R[90]=R[90]+1    ;
  72:  UFRAME_NUM=1 ;
  73:  UTOOL_NUM=1 ;
  74:L P[11] 200mm/sec FINE    ;
  75:  UFRAME_NUM=0 ;
  76:  UTOOL_NUM=9 ;
  77:  PR[R[90]]=LPOS    ;
  78:  R[90]=R[90]+1    ;
  79:  UFRAME_NUM=1 ;
  80:  UTOOL_NUM=1 ;
  81:L P[12] 1000mm/sec FINE    ;
  82:  UFRAME_NUM=0 ;
  83:  UTOOL_NUM=9 ;
  84:  PR[R[90]]=LPOS    ;
  85:  R[90]=R[90]+1    ;
  86:  UFRAME_NUM=1 ;
  87:  UTOOL_NUM=1 ;
  88:L P[13] 200mm/sec FINE    ;
  89:  UFRAME_NUM=0 ;
  90:  UTOOL_NUM=9 ;
  91:  PR[R[90]]=LPOS    ;
  92:  R[90]=R[90]+1    ;
  93:  UFRAME_NUM=1 ;
  94:  UTOOL_NUM=1 ;
  95:L P[14] 200mm/sec FINE    ;
  96:  UFRAME_NUM=0 ;
  97:  UTOOL_NUM=9 ;
  98:  PR[R[90]]=LPOS    ;
  99:  R[90]=R[90]+1    ;
 100:  UFRAME_NUM=1 ;
 101:  UTOOL_NUM=1 ;
 102:J P[15] 22% FINE    ;
 103:  UFRAME_NUM=0 ;
 104:  UTOOL_NUM=9 ;
 105:  PR[R[90]]=LPOS    ;
 106:  R[90]=R[90]+1    ;
 107:  UFRAME_NUM=1 ;
 108:  UTOOL_NUM=1 ;
 109:L P[16] 200mm/sec FINE    ;
 110:  UFRAME_NUM=0 ;
 111:  UTOOL_NUM=9 ;
 112:  PR[R[90]]=LPOS    ;
 113:  R[90]=R[90]+1    ;
 114:  UFRAME_NUM=1 ;
 115:  UTOOL_NUM=1 ;
 116:L P[17] 200mm/sec FINE    ;
 117:  UFRAME_NUM=0 ;
 118:  UTOOL_NUM=9 ;
 119:  PR[R[90]]=LPOS    ;
 120:  R[90]=R[90]+1    ;
 121:  UFRAME_NUM=1 ;
 122:  UTOOL_NUM=1 ;
 123:  UFRAME_NUM=2 ;
 124:  UTOOL_NUM=2 ;
 125:J P[18] 22% FINE    ;
 126:  UFRAME_NUM=0 ;
 127:  UTOOL_NUM=9 ;
 128:  PR[R[90]]=LPOS    ;
 129:  R[90]=R[90]+1    ;
 130:  UFRAME_NUM=2 ;
 131:  UTOOL_NUM=2 ;
 132:L P[19] 200mm/sec FINE    ;
 133:  UFRAME_NUM=0 ;
 134:  UTOOL_NUM=9 ;
 135:  PR[R[90]]=LPOS    ;
 136:  R[90]=R[90]+1    ;
 137:  UFRAME_NUM=2 ;
 138:  UTOOL_NUM=2 ;
 139:L P[20] 200mm/sec FINE    ;
 140:  UFRAME_NUM=0 ;
 141:  UTOOL_NUM=9 ;
 142:  PR[R[90]]=LPOS    ;
 143:  R[90]=R[90]+1    ;
 144:  UFRAME_NUM=2 ;
 145:  UTOOL_NUM=2 ;
 146:  UFRAME_NUM=1 ;
 147:  UTOOL_NUM=1 ;
 148:J P[21] 22% FINE    ;
 149:  UFRAME_NUM=0 ;
 150:  UTOOL_NUM=9 ;
 151:  PR[R[90]]=LPOS    ;
 152:  R[90]=R[90]+1    ;
 153:  UFRAME_NUM=1 ;
 154:  UTOOL_NUM=1 ;
 155:L P[22] 200mm/sec FINE    ;
 156:  UFRAME_NUM=0 ;
 157:  UTOOL_NUM=9 ;
 158:  PR[R[90]]=LPOS    ;
 159:  R[90]=R[90]+1    ;
 160:  UFRAME_NUM=1 ;
 161:  UTOOL_NUM=1 ;
 162:L P[23] 200mm/sec FINE    ;
 163:  UFRAME_NUM=0 ;
 164:  UTOOL_NUM=9 ;
 165:  PR[R[90]]=LPOS    ;
 166:  R[90]=R[90]+1    ;
 167:  UFRAME_NUM=1 ;
 168:  UTOOL_NUM=1 ;
 169:L P[24] 500mm/sec FINE    ;
 170:  UFRAME_NUM=0 ;
 171:  UTOOL_NUM=9 ;
 172:  PR[R[90]]=LPOS    ;
 173:  R[90]=R[90]+1    ;
 174:  UFRAME_NUM=1 ;
 175:  UTOOL_NUM=1 ;
 176:J P[25] 22% FINE    ;
 177:  UFRAME_NUM=0 ;
 178:  UTOOL_NUM=9 ;
 179:  PR[R[90]]=LPOS    ;
 180:  R[90]=R[90]+1    ;
 181:  UFRAME_NUM=1 ;
 182:  UTOOL_NUM=1 ;
 183:L P[26] 200mm/sec FINE    ;
 184:  UFRAME_NUM=0 ;
 185:  UTOOL_NUM=9 ;
 186:  PR[R[90]]=LPOS    ;
 187:  R[90]=R[90]+1    ;
 188:  UFRAME_NUM=1 ;
 189:  UTOOL_NUM=1 ;
 190:L P[27] 1000mm/sec FINE    ;
 191:  UFRAME_NUM=0 ;
 192:  UTOOL_NUM=9 ;
 193:  PR[R[90]]=LPOS    ;
 194:  R[90]=R[90]+1    ;
 195:  UFRAME_NUM=1 ;
 196:  UTOOL_NUM=1 ;
 197:L P[28] 500mm/sec FINE    ;
 198:  UFRAME_NUM=0 ;
 199:  UTOOL_NUM=9 ;
 200:  PR[R[90]]=LPOS    ;
 201:  R[90]=R[90]+1    ;
 202:  UFRAME_NUM=1 ;
 203:  UTOOL_NUM=1 ;
 204:L P[29] 500mm/sec FINE    ;
 205:  UFRAME_NUM=0 ;
 206:  UTOOL_NUM=9 ;
 207:  PR[R[90]]=LPOS    ;
 208:  R[90]=R[90]+1    ;
 209:  UFRAME_NUM=1 ;
 210:  UTOOL_NUM=1 ;
 211:J P[30] 22% FINE    ;
 212:  UFRAME_NUM=0 ;
 213:  UTOOL_NUM=9 ;
 214:  PR[R[90]]=LPOS    ;
 215:  R[90]=R[90]+1    ;
 216:  UFRAME_NUM=1 ;
 217:  UTOOL_NUM=1 ;
 218:L P[31] 200mm/sec FINE    ;
 219:  UFRAME_NUM=0 ;
 220:  UTOOL_NUM=9 ;
 221:  PR[R[90]]=LPOS    ;
 222:  R[90]=R[90]+1    ;
 223:  UFRAME_NUM=1 ;
 224:  UTOOL_NUM=1 ;
 225:L P[32] 1000mm/sec FINE    ;
 226:  UFRAME_NUM=0 ;
 227:  UTOOL_NUM=9 ;
 228:  PR[R[90]]=LPOS    ;
 229:  R[90]=R[90]+1    ;
 230:  UFRAME_NUM=1 ;
 231:  UTOOL_NUM=1 ;
 232:L P[33] 500mm/sec FINE    ;
 233:  UFRAME_NUM=0 ;
 234:  UTOOL_NUM=9 ;
 235:  PR[R[90]]=LPOS    ;
 236:  R[90]=R[90]+1    ;
 237:  UFRAME_NUM=1 ;
 238:  UTOOL_NUM=1 ;
 239:L P[34] 500mm/sec FINE    ;
 240:  UFRAME_NUM=0 ;
 241:  UTOOL_NUM=9 ;
 242:  PR[R[90]]=LPOS    ;
 243:  R[90]=R[90]+1    ;
 244:  UFRAME_NUM=1 ;
 245:  UTOOL_NUM=1 ;
 246:J P[35] 22% FINE    ;
 247:  UFRAME_NUM=0 ;
 248:  UTOOL_NUM=9 ;
 249:  PR[R[90]]=LPOS    ;
 250:  R[90]=R[90]+1    ;
 251:  UFRAME_NUM=1 ;
 252:  UTOOL_NUM=1 ;
 253:L P[36] 200mm/sec FINE    ;
 254:  UFRAME_NUM=0 ;
 255:  UTOOL_NUM=9 ;
 256:  PR[R[90]]=LPOS    ;
 257:  R[90]=R[90]+1    ;
 258:  UFRAME_NUM=1 ;
 259:  UTOOL_NUM=1 ;
 260:L P[37] 1000mm/sec FINE    ;
 261:  UFRAME_NUM=0 ;
 262:  UTOOL_NUM=9 ;
 263:  PR[R[90]]=LPOS    ;
 264:  R[90]=R[90]+1    ;
 265:  UFRAME_NUM=1 ;
 266:  UTOOL_NUM=1 ;
 267:L P[38] 500mm/sec FINE    ;
 268:  UFRAME_NUM=0 ;
 269:  UTOOL_NUM=9 ;
 270:  PR[R[90]]=LPOS    ;
 271:  R[90]=R[90]+1    ;
 272:  UFRAME_NUM=1 ;
 273:  UTOOL_NUM=1 ;
 274:L P[39] 500mm/sec FINE    ;
 275:  UFRAME_NUM=0 ;
 276:  UTOOL_NUM=9 ;
 277:  PR[R[90]]=LPOS    ;
 278:  R[90]=R[90]+1    ;
 279:  UFRAME_NUM=1 ;
 280:  UTOOL_NUM=1 ;
 281:J P[40] 22% FINE    ;
 282:  UFRAME_NUM=0 ;
 283:  UTOOL_NUM=9 ;
 284:  PR[R[90]]=LPOS    ;
 285:  R[90]=R[90]+1    ;
 286:  UFRAME_NUM=1 ;
 287:  UTOOL_NUM=1 ;
 288:L P[41] 200mm/sec FINE    ;
 289:  UFRAME_NUM=0 ;
 290:  UTOOL_NUM=9 ;
 291:  PR[R[90]]=LPOS    ;
 292:  R[90]=R[90]+1    ;
 293:  UFRAME_NUM=1 ;
 294:  UTOOL_NUM=1 ;
 295:L P[42] 1000mm/sec FINE    ;
 296:  UFRAME_NUM=0 ;
 297:  UTOOL_NUM=9 ;
 298:  PR[R[90]]=LPOS    ;
 299:  R[90]=R[90]+1    ;
 300:  UFRAME_NUM=1 ;
 301:  UTOOL_NUM=1 ;
 302:L P[43] 500mm/sec FINE    ;
 303:  UFRAME_NUM=0 ;
 304:  UTOOL_NUM=9 ;
 305:  PR[R[90]]=LPOS    ;
 306:  R[90]=R[90]+1    ;
 307:  UFRAME_NUM=1 ;
 308:  UTOOL_NUM=1 ;
/POS
P[1]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    60.000  mm,	Y =    20.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[2]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    60.000  mm,	Y =    20.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[3]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    70.000  mm,	Y =     0.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[4]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   180.000  mm,	Y =   170.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[5]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   180.000  mm,	Y =   170.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[6]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   190.000  mm,	Y =   150.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[7]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   180.000  mm,	Y =   120.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[8]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   180.000  mm,	Y =   120.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[9]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   190.000  mm,	Y =   100.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[10]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   210.000  mm,	Y =   120.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[11]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   210.000  mm,	Y =   120.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[12]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   220.000  mm,	Y =   100.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[13]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    60.000  mm,	Y =    20.000  mm,	Z =   280.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[14]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    70.000  mm,	Y =    25.000  mm,	Z =   270.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   -30.000 deg
};
P[15]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    60.000  mm,	Y =    20.000  mm,	Z =   270.000  mm,
	W =  -173.763 deg,	P =     7.817 deg,	R =   -14.153 deg
};
P[16]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   180.000  mm,	Y =   120.000  mm,	Z =   275.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[17]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   185.000  mm,	Y =   120.000  mm,	Z =   225.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[18]{
   GP1:
	UF : 2, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =    60.000  mm,	Y =    20.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[19]{
   GP1:
	UF : 2, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =    60.000  mm,	Y =    20.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[20]{
   GP1:
	UF : 2, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =   120.000  mm,	Y =    40.000  mm,	Z =   240.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[21]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   180.000  mm,	Y =   120.000  mm,	Z =   300.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[22]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   180.000  mm,	Y =   120.000  mm,	Z =   260.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[23]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   120.000  mm,	Y =    40.000  mm,	Z =   240.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[24]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =   -40.000  mm,	Z =   230.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[25]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =   -40.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[26]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =   -40.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[27]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    50.000  mm,	Y =   -60.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[28]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    45.000  mm,	Y =   -40.000  mm,	Z =   245.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   -20.000 deg
};
P[29]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   100.000  mm,	Y =   -40.000  mm,	Z =   230.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[30]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   100.000  mm,	Y =   -40.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[31]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   100.000  mm,	Y =   -40.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[32]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   110.000  mm,	Y =   -60.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[33]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   105.000  mm,	Y =   -40.000  mm,	Z =   245.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   -20.000 deg
};
P[34]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    60.000  mm,	Z =   230.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[35]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    60.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[36]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    60.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[37]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    50.000  mm,	Y =    40.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[38]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    45.000  mm,	Y =    60.000  mm,	Z =   245.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   -20.000 deg
};
P[39]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   100.000  mm,	Y =    60.000  mm,	Z =   230.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[40]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   100.000  mm,	Y =    60.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[41]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   100.000  mm,	Y =    60.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[42]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   110.000  mm,	Y =    40.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[43]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   105.000  mm,	Y =    60.000  mm,	Z =   245.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   -20.000 deg
};
/END
