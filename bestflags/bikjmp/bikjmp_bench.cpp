/*
 * A chess benchmark, derived from the UCI engine BikJump.
 * @author ajcbik@google.com (Aart Bik)
 *
 * This benchmark executes all computations of the actual chess
 * engine, but using a deterministic fixed depth search to enable
 * testing correctness as well as performance. This work is derived
 * from UCI chess engine BikJump. Therefore, this application as a
 * whole cannot be (re)used without explicit permission of the author.
 **/

#include <assert.h>
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

typedef unsigned char      uint08;
typedef unsigned short     uint16;
typedef unsigned int       uint32;
typedef unsigned long long uint64;

#define TRANSON
#define NULLMOV
#define PVS

#define MAXDP 128
#define MAXMV 256
#define HISTO 1024

#define SECOND (1000)
#define ClockstoMs(y) (  (uint32)((y) /(CLOCKS_PER_SEC/SECOND)) )

/* Board */

typedef struct board_s {
  uint32 board[10*12];
  uint32 state;
  uint32 plycnt;
  uint32 r50cnt;
  uint64 zobrist;
  int    wk, bk;
  uint32 auxB[2*16];
  uint32 auxL[10*12];
  int auxw;
  int auxb;
} BOARD;

/* Pieces */

#define EMPTY    0x00

#define WPAWN    0x10
#define WKNIGHT  0x11
#define WBISHOP  0x12
#define WROOK    0x14
#define WQUEEN   0x16
#define WKING    0x18
#define BPAWN    0x20
#define BKNIGHT  0x21
#define BBISHOP  0x22
#define BROOK    0x24
#define BQUEEN   0x26
#define BKING    0x28

#define WHITE    0x10
#define BLACK    0x20

#define WDIAG    0x12
#define WSTRT    0x14
#define BDIAG    0x22
#define BSTRT    0x24

#define FULL     0x40

#define is_whiteI(p) ((p)&(WHITE|FULL)) /* including FULL */
#define is_blackI(p) ((p)&(BLACK|FULL))
#define is_whiteE(p) ((p)&(WHITE))      /* excluding FULL */
#define is_blackE(p) ((p)&(BLACK))

/* States */

#define STATE_enp(s) ((s)&0x000f)
#define STATE_wck(s) ((s)&0x0010)
#define STATE_wcq(s) ((s)&0x0020)
#define STATE_bck(s) ((s)&0x0040)
#define STATE_bcq(s) ((s)&0x0080)
#define STATE_wtm(s) ((s)&0x0100)==0

#define STATE_SET_WTM(s)    ((s)=(s)&~0x0100)
#define STATE_SET_BTM(s)    ((s)=(s)| 0x0100)

#define STATE_NEW_MOV(s)    ((s)=(((s)|0x000f)^0x0100))

#define STATE_SET_ENP(s,e)  ((s)=(((s)&~0x000f)|(e)))

#define STATE_CLR_WC2(s)    ((s)=((s)&~0x030))
#define STATE_CLR_WCK(s)    ((s)=((s)&~0x010))
#define STATE_CLR_WCQ(s)    ((s)=((s)&~0x020))
#define STATE_SET_WCK(s)    ((s)=((s)| 0x010))
#define STATE_SET_WCQ(s)    ((s)=((s)| 0x020))

#define STATE_CLR_BC2(s)    ((s)=((s)&~0x0c0))
#define STATE_CLR_BCK(s)    ((s)=((s)&~0x040))
#define STATE_CLR_BCQ(s)    ((s)=((s)&~0x080))
#define STATE_SET_BCK(s)    ((s)=((s)| 0x040))
#define STATE_SET_BCQ(s)    ((s)=((s)| 0x080))

/* Moves */

typedef uint32 MOVES[MAXMV];

#define FROM     0x000000ff
#define TO       0x0000ff00
#define PROMO    0x003f0000
#define CAP      0x3f000000
#define CHECK    0x00400000
#define CASTLE   0x40000000
#define ENPASS   0x80000000

/* Search Stats and Controls */

static BOARD   interb;

static uint32  nodes  = 0;
static uint32  curdp  = 0;
static uint32  seldp  = 0;
static uint32  extdp  = 0;

static uint64  history[HISTO];
static uint32  killerm[MAXDP];

#define Z1 78  /* 1+98-21       */
#define Z2 32  /* 1+BKING-WPAWN */

static uint64  zobrist[Z1][Z2];
static uint64  zobrist2 = 0;

#define ZOB(x,y) (zobrist[(x)-21][(y)-WPAWN])

/* Transposition Tables */

#define TRANSMASK1 0x0fff
#define TRANSMASK2 0x3000
#define TRANSALPHA 0x1000
#define TRANSBETA  0x2000
#define TRANSEXACT 0x3000
#define TRANSNONE  999999

typedef struct trans_t {
  uint64 key;
  uint16 depth;
  short  val;
  uint32 best;
} TRANSTB;

static TRANSTB *transpos   = NULL;
static uint32   transmask0 = 0;

/* Piece Placement Tables */

static const uint08 placeminor[10*12] = {
  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
  0,  0,  1,  2,  3,  3,  2,  1,  0,  0,
  0,  1,  4,  5,  6,  6,  5,  4,  1,  0,
  0,  2,  5,  7,  8,  8,  7,  5,  2,  0,
  0,  3,  6,  9, 11, 11,  9,  6,  3,  0,
  0,  3,  6,  9, 11, 11,  9,  6,  3,  0,
  0,  2,  5,  7,  8,  8,  7,  5,  2,  0,
  0,  1,  4,  5,  6,  6,  5,  4,  1,  0,
  0,  0,  1,  2,  3,  3,  2,  1,  0,  0,
  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
  0,  0,  0,  0,  0,  0,  0,  0,  0,  0
};

static const uint08 placex[10*12] = {
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 1, 2, 3, 4, 5, 6, 7, 0,
  0, 0, 1, 2, 3, 4, 5, 6, 7, 0,
  0, 0, 1, 2, 3, 4, 5, 6, 7, 0,
  0, 0, 1, 2, 3, 4, 5, 6, 7, 0,
  0, 0, 1, 2, 3, 4, 5, 6, 7, 0,
  0, 0, 1, 2, 3, 4, 5, 6, 7, 0,
  0, 0, 1, 2, 3, 4, 5, 6, 7, 0,
  0, 0, 1, 2, 3, 4, 5, 6, 7, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
};

static const uint08 placey[10*12] = {
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 1, 1, 1, 1, 1, 1, 1, 1, 0,
  0, 2, 2, 2, 2, 2, 2, 2, 2, 0,
  0, 3, 3, 3, 3, 3, 3, 3, 3, 0,
  0, 4, 4, 4, 4, 4, 4, 4, 4, 0,
  0, 5, 5, 5, 5, 5, 5, 5, 5, 0,
  0, 6, 6, 6, 6, 6, 6, 6, 6, 0,
  0, 7, 7, 7, 7, 7, 7, 7, 7, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0
};

static const uint32 leftmidright[8] = {
  0x03, 0x07, 0x0e, 0x1c, 0x38, 0x70, 0xe0,
};

static const uint08 colorb[10*12] = {
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 1, 0, 1, 0, 1, 0, 1, 0, 0,
  0, 0, 1, 0, 1, 0, 1, 0, 1, 0,
  0, 1, 0, 1, 0, 1, 0, 1, 0, 0,
  0, 0, 1, 0, 1, 0, 1, 0, 1, 0,
  0, 1, 0, 1, 0, 1, 0, 1, 0, 0,
  0, 0, 1, 0, 1, 0, 1, 0, 1, 0,
  0, 1, 0, 1, 0, 1, 0, 1, 0, 0,
  0, 0, 1, 0, 1, 0, 1, 0, 1, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0
};

static const uint08 pawnval[256] = {
    0 /*00000000*/,    3 /*00000001*/,    4 /*00000010*/,    7 /*00000011*/,
    6 /*00000100*/,    7 /*00000101*/,   10 /*00000110*/,   13 /*00000111*/,
    7 /*00001000*/,    8 /*00001001*/,    9 /*00001010*/,   12 /*00001011*/,
   13 /*00001100*/,   14 /*00001101*/,   17 /*00001110*/,   20 /*00001111*/,
    7 /*00010000*/,    8 /*00010001*/,    9 /*00010010*/,   12 /*00010011*/,
   11 /*00010100*/,   12 /*00010101*/,   15 /*00010110*/,   18 /*00010111*/,
   14 /*00011000*/,   15 /*00011001*/,   16 /*00011010*/,   19 /*00011011*/,
   20 /*00011100*/,   21 /*00011101*/,   24 /*00011110*/,   27 /*00011111*/,
    6 /*00100000*/,    7 /*00100001*/,    8 /*00100010*/,   11 /*00100011*/,
   10 /*00100100*/,   11 /*00100101*/,   14 /*00100110*/,   17 /*00100111*/,
   11 /*00101000*/,   12 /*00101001*/,   13 /*00101010*/,   16 /*00101011*/,
   17 /*00101100*/,   18 /*00101101*/,   21 /*00101110*/,   24 /*00101111*/,
   13 /*00110000*/,   14 /*00110001*/,   15 /*00110010*/,   18 /*00110011*/,
   17 /*00110100*/,   18 /*00110101*/,   21 /*00110110*/,   24 /*00110111*/,
   20 /*00111000*/,   21 /*00111001*/,   22 /*00111010*/,   25 /*00111011*/,
   26 /*00111100*/,   27 /*00111101*/,   30 /*00111110*/,   33 /*00111111*/,
    4 /*01000000*/,    5 /*01000001*/,    6 /*01000010*/,    9 /*01000011*/,
    8 /*01000100*/,    9 /*01000101*/,   12 /*01000110*/,   15 /*01000111*/,
    9 /*01001000*/,   10 /*01001001*/,   11 /*01001010*/,   14 /*01001011*/,
   15 /*01001100*/,   16 /*01001101*/,   19 /*01001110*/,   22 /*01001111*/,
    9 /*01010000*/,   10 /*01010001*/,   11 /*01010010*/,   14 /*01010011*/,
   13 /*01010100*/,   14 /*01010101*/,   17 /*01010110*/,   20 /*01010111*/,
   16 /*01011000*/,   17 /*01011001*/,   18 /*01011010*/,   21 /*01011011*/,
   22 /*01011100*/,   23 /*01011101*/,   26 /*01011110*/,   29 /*01011111*/,
   10 /*01100000*/,   11 /*01100001*/,   12 /*01100010*/,   15 /*01100011*/,
   14 /*01100100*/,   15 /*01100101*/,   18 /*01100110*/,   21 /*01100111*/,
   15 /*01101000*/,   16 /*01101001*/,   17 /*01101010*/,   20 /*01101011*/,
   21 /*01101100*/,   22 /*01101101*/,   25 /*01101110*/,   28 /*01101111*/,
   17 /*01110000*/,   18 /*01110001*/,   19 /*01110010*/,   22 /*01110011*/,
   21 /*01110100*/,   22 /*01110101*/,   25 /*01110110*/,   28 /*01110111*/,
   24 /*01111000*/,   25 /*01111001*/,   26 /*01111010*/,   29 /*01111011*/,
   30 /*01111100*/,   31 /*01111101*/,   34 /*01111110*/,   37 /*01111111*/,
    3 /*10000000*/,    4 /*10000001*/,    5 /*10000010*/,    8 /*10000011*/,
    7 /*10000100*/,    8 /*10000101*/,   11 /*10000110*/,   14 /*10000111*/,
    8 /*10001000*/,    9 /*10001001*/,   10 /*10001010*/,   13 /*10001011*/,
   14 /*10001100*/,   15 /*10001101*/,   18 /*10001110*/,   21 /*10001111*/,
    8 /*10010000*/,    9 /*10010001*/,   10 /*10010010*/,   13 /*10010011*/,
   12 /*10010100*/,   13 /*10010101*/,   16 /*10010110*/,   19 /*10010111*/,
   15 /*10011000*/,   16 /*10011001*/,   17 /*10011010*/,   20 /*10011011*/,
   21 /*10011100*/,   22 /*10011101*/,   25 /*10011110*/,   28 /*10011111*/,
    7 /*10100000*/,    8 /*10100001*/,    9 /*10100010*/,   12 /*10100011*/,
   11 /*10100100*/,   12 /*10100101*/,   15 /*10100110*/,   18 /*10100111*/,
   12 /*10101000*/,   13 /*10101001*/,   14 /*10101010*/,   17 /*10101011*/,
   18 /*10101100*/,   19 /*10101101*/,   22 /*10101110*/,   25 /*10101111*/,
   14 /*10110000*/,   15 /*10110001*/,   16 /*10110010*/,   19 /*10110011*/,
   18 /*10110100*/,   19 /*10110101*/,   22 /*10110110*/,   25 /*10110111*/,
   21 /*10111000*/,   22 /*10111001*/,   23 /*10111010*/,   26 /*10111011*/,
   27 /*10111100*/,   28 /*10111101*/,   31 /*10111110*/,   34 /*10111111*/,
    7 /*11000000*/,    8 /*11000001*/,    9 /*11000010*/,   12 /*11000011*/,
   11 /*11000100*/,   12 /*11000101*/,   15 /*11000110*/,   18 /*11000111*/,
   12 /*11001000*/,   13 /*11001001*/,   14 /*11001010*/,   17 /*11001011*/,
   18 /*11001100*/,   19 /*11001101*/,   22 /*11001110*/,   25 /*11001111*/,
   12 /*11010000*/,   13 /*11010001*/,   14 /*11010010*/,   17 /*11010011*/,
   16 /*11010100*/,   17 /*11010101*/,   20 /*11010110*/,   23 /*11010111*/,
   19 /*11011000*/,   20 /*11011001*/,   21 /*11011010*/,   24 /*11011011*/,
   25 /*11011100*/,   26 /*11011101*/,   29 /*11011110*/,   32 /*11011111*/,
   13 /*11100000*/,   14 /*11100001*/,   15 /*11100010*/,   18 /*11100011*/,
   17 /*11100100*/,   18 /*11100101*/,   21 /*11100110*/,   24 /*11100111*/,
   18 /*11101000*/,   19 /*11101001*/,   20 /*11101010*/,   23 /*11101011*/,
   24 /*11101100*/,   25 /*11101101*/,   28 /*11101110*/,   31 /*11101111*/,
   20 /*11110000*/,   21 /*11110001*/,   22 /*11110010*/,   25 /*11110011*/,
   24 /*11110100*/,   25 /*11110101*/,   28 /*11110110*/,   31 /*11110111*/,
   27 /*11111000*/,   28 /*11111001*/,   29 /*11111010*/,   32 /*11111011*/,
   33 /*11111100*/,   34 /*11111101*/,   37 /*11111110*/,   40 /*11111111*/,
};

#define S08(x) ((x)<<8)

/*************************
 **** Auxiliary Board ****
 *************************/

/* Add to sparse list */

static inline void auxAdd(BOARD *b, int c, int k)
{
  if (c == 0) {
    int l = b->auxw++;
    b->auxB[l] = k;
    b->auxL[k] = l;
    assert(b->auxw <= 16);
  }
  else {
    int l = b->auxb++;
    b->auxB[16+l] = k;
    b->auxL[k] = 16+l;
    assert(b->auxb <= 16);
  }
}

/* Remove from sparse list */

static inline void auxDel(BOARD *b, int c, int k)
{
  if (c == 0) {
    int l = b->auxL[k];
    int m = --b->auxw;
    if (l != m) {
      k = b->auxB[m];
      b->auxB[l] = k;
      b->auxL[k] = l;
    }
    assert(b->auxw >= 0);
  }
  else {
    int l = b->auxL[k];
    int m = --b->auxb + 16;
    if (l != m) {
      k = b->auxB[m];
      b->auxB[l] = b->auxB[m];
      b->auxL[k] = l;
    }
    assert(b->auxb >= 0);
  }
}

/* Initialize sparse list */

static void auxInit(BOARD *b)
{
  int k;
  b->auxw = 0;
  b->auxb = 0;
  for (k = 21; k <= 98; k++) {
    uint32 bb = b->board[k];
    if (bb & WHITE) {
      auxAdd(b, 0, k);
    }
    else if (bb & BLACK) {
      auxAdd(b, 1, k);
    }
  }
  assert(b->auxw <= 16);
  assert(b->auxb <= 16);
}

/***************************
 **** Zobrist Utilities ****
 ***************************/

/* Initialize Zobrist Data */

static void initZobrist(void)
{
  int i, j;

  for (i = 0; i < Z1; i++) {
    for (j = 0; j < Z2; j++) {
      zobrist[i][j] = ( ((uint64) rand())        ^
                       (((uint64) rand()) << 15) ^
                       (((uint64) rand()) << 30) ^
                       (((uint64) rand()) << 45) ^
                       (((uint64) rand()) << 60) );
    }
  }
  zobrist2 = (  ((uint64) rand())        ^
               (((uint64) rand()) << 15) ^
               (((uint64) rand()) << 30) ^
               (((uint64) rand()) << 45) ^
               (((uint64) rand()) << 60) );
}

/* Compute Zobrist Key */

static uint64 compZobrist(BOARD *b)
{
  uint64 zob = (STATE_wtm(b->state)) ? 0 : zobrist2;
  int    k;

  for (k = 21; k <= 98; k++) {
    if (b->board[k] & (WHITE|BLACK)) { /* DIRTY SPARSE */
      zob ^= ZOB(k,b->board[k]);
    }
  } /* for */

  return zob;
}

/* Record Position */

static inline void recPos(BOARD *b)
{
  if (b->plycnt < HISTO) {
    history[b->plycnt++] = b->zobrist;
  }
}

/* Test Threefold Repetition
 * NOTE: technically, e.p. and castling rights should be
 *       incorporated in zobrist representation; ah well!
 * NOTE: the sloppy version claims draw on first repeat;
 *       this detects forcable repeats earlier, avoids
 *       annoying play, and allows earlier transposition
 */

static inline int repPosSloppy(BOARD *b)
{
  if (b->r50cnt >= 4) {
    int    c  = b->r50cnt >> 1, p = b->plycnt, i;
    uint64 zo = b->zobrist;
    for (i = 0; i < c; i++) {
      p -= 2;
      if (history[p] == zo) {
        return 1;
      }
    } /* for */
  }

  return 0;
}


/*********************************
 **** Transposition Utilities ****
 *********************************/

/* Free */

static void freeTrans(void)
{
  if (transpos) {
    free(transpos);
  }
  transpos   = NULL;
  transmask0 = 0;
}

/* Allocate */

static void allocTrans(uint32 meg)
{
  freeTrans();

  /* stick to lowest power of two allowed */
  if      (meg >= 1024) meg = 1024*1024*1024;
  else if (meg >=  512) meg = 1024*1024*512;
  else if (meg >=  256) meg = 1024*1024*256;
  else if (meg >=  128) meg = 1024*1024*128;
  else if (meg >=   64) meg = 1024*1024*64;
  else if (meg >=   32) meg = 1024*1024*32;
  else if (meg >=   16) meg = 1024*1024*16;
  else if (meg >=    8) meg = 1024*1024*8;
  else if (meg >=    4) meg = 1024*1024*4;
  else if (meg >=    2) meg = 1024*1024*2;
  else                  meg = 1024*1024;

  /* allocate */
  transpos   = (TRANSTB *) malloc(meg);
  transmask0 = (meg / sizeof(struct trans_t)) - 1;

  if (!transpos) {
    exit(1);
  }
  memset(transpos, 0, meg);
}

/* Lookup */

static inline int lookupTrans(uint64 z, uint32 dp, uint32 dm, int alpha, int beta)
{
  uint32 indx = (((uint32)z) & transmask0);
  if (transpos[indx].key == z) {
    uint32 ld = (transpos[indx].depth & TRANSMASK1);
    assert(dp <= dm);
    /* Use the killer move data structure to make sure
     * hash move is searched first at this depth.
     */
    uint32 best = transpos[indx].best;
    if (best) {
      if (dp < MAXDP) killerm[dp] = best;
    }
    if (ld >= (dm-dp)) {
      uint32 lc = (transpos[indx].depth & TRANSMASK2);
      int    lv = (transpos[indx].val);
      switch (lc) {
        case TRANSALPHA: return (lv <= alpha) ? alpha : TRANSNONE;
        case TRANSBETA:  return (lv >= beta)  ? beta  : TRANSNONE;
        default:
          assert(lc == TRANSEXACT);
          return lv;
      } /* switch */
    }
  }
  return TRANSNONE;
}

/* Insert */

static inline void insertTrans(uint64 z, uint32 dp, uint32 dm, uint32 c, int v, uint32 best)
{
  uint32 indx = (((uint32)z) & transmask0);
  assert(-32767 <= v && v <= 32767);
  /* adjust mate values for use in cut-off only (but at any depth) */
  if (v <= -32000) {
    switch (c) {
      case TRANSEXACT: c = TRANSALPHA;
      case TRANSALPHA: v = -32000; break;
      default:         return;
    }
    dp = 0; dm = MAXDP;
  }
  else if (v >= 32000) {
    switch (c) {
      case TRANSEXACT: c = TRANSBETA;
      case TRANSBETA:  v = 32000; break;
      default:         return;
    }
    dp = 0; dm = MAXDP;
  }
  /* insert */
  assert(dp <= dm);
  transpos[indx].key   = z;
  transpos[indx].depth = (dm-dp) | c;
  transpos[indx].val   = v;
  transpos[indx].best  = best;
}

/* Clear Board */

static void clearBoard(BOARD *b)
{
  int x, y, k;

  for (k = 0; k < 20; k++) {
    b->board[k] = FULL;
  }
  for (k = 20, y = 0; y < 8; y++) {
    b->board[k++] = FULL;
    for (x = 0; x < 8; x++) {
      b->board[k++] = EMPTY;
    }
    b->board[k++] = FULL;
  }
  for (k = 100; k < 120; k++) {
    b->board[k] = FULL;
  }

  b->state   = 0x000f;
  b->plycnt  = 0;
  b->r50cnt  = 0;
  b->zobrist = 0;
  b->wk      = 0; /* not on board! */
  b->bk      = 0; /* not on board! */
}

/**************************
 **** Attack Utilities ****
 **************************/

/* Test White Pawn Attack */

static inline int wpattacks(BOARD *b, int k)
{
  if (b->board[k-11] == WPAWN || b->board[k-9] == WPAWN) {
    return 1;
  }
  return 0;
}

/* Test White Knight Attack */

static inline int whattacks(BOARD *b, int k)
{
  if (b->board[k-21] == WKNIGHT || b->board[k-19] == WKNIGHT ||
      b->board[k-12] == WKNIGHT || b->board[k-8]  == WKNIGHT ||
      b->board[k+8]  == WKNIGHT || b->board[k+12] == WKNIGHT ||
      b->board[k+19] == WKNIGHT || b->board[k+21] == WKNIGHT) {
    return 1;
  }
  return 0;
}

/* Test White King Attack */

static inline int wkattacks(BOARD *b, int k)
{
  if (b->board[k-11] == WKING || b->board[k-10] == WKING ||
      b->board[k-9]  == WKING || b->board[k-1]  == WKING ||
      b->board[k+1]  == WKING || b->board[k+9]  == WKING ||
      b->board[k+10] == WKING || b->board[k+11] == WKING) {
    return 1;
  }
  return 0;
}

/* Test White Diagonal Attack */

static inline int wdattacks(BOARD *b, int k)
{
  int kk;

  kk = k; do {
    kk -= 11;
  } while (b->board[kk] == EMPTY);
  if ((b->board[kk] & WDIAG) == WDIAG) return 1;

  kk = k; do {
    kk -= 9;
  } while (b->board[kk] == EMPTY);
  if ((b->board[kk] & WDIAG) == WDIAG) return 1;

  kk = k; do {
    kk += 9;
  } while (b->board[kk] == EMPTY);
  if ((b->board[kk] & WDIAG) == WDIAG) return 1;

  kk = k; do {
    kk += 11;
  } while (b->board[kk] == EMPTY);
  if ((b->board[kk] & WDIAG) == WDIAG) return 1;

  return 0;
}

/* Test White Straight Attack */

static inline int wsattacks(BOARD *b, int k)
{
  int kk;

  kk = k; do {
    kk -= 10;
  } while (b->board[kk] == EMPTY);
  if ((b->board[kk] & WSTRT) == WSTRT) return 1;

  kk = k; do {
    kk -= 1;
  } while (b->board[kk] == EMPTY);
  if ((b->board[kk] & WSTRT) == WSTRT) return 1;

  kk = k; do {
    kk += 1;
  } while (b->board[kk] == EMPTY);
  if ((b->board[kk] & WSTRT) == WSTRT) return 1;

  kk = k; do {
    kk += 10;
  } while (b->board[kk] == EMPTY);
  if ((b->board[kk] & WSTRT) == WSTRT) return 1;

  return 0;
}

/* Test White Attack (excluding en passant captures) */

static inline int wattacks(BOARD *b, int k)
{
  return (wpattacks(b, k) || whattacks(b, k) || wkattacks(b, k) ||
                             wdattacks(b, k) || wsattacks(b, k));
}

/* Test Black Pawn Attack */

static inline int bpattacks(BOARD *b, int k)
{
  if (b->board[k+9] == BPAWN || b->board[k+11] == BPAWN) {
    return 1;
  }
  return 0;
}

/* Test Black Knight Attack */

static inline int bhattacks(BOARD *b, int k)
{
  if (b->board[k-21] == BKNIGHT || b->board[k-19] == BKNIGHT ||
      b->board[k-12] == BKNIGHT || b->board[k-8]  == BKNIGHT ||
      b->board[k+8]  == BKNIGHT || b->board[k+12] == BKNIGHT ||
      b->board[k+19] == BKNIGHT || b->board[k+21] == BKNIGHT) {
    return 1;
  }
  return 0;
}

/* Test Black King Attack */

static inline int bkattacks(BOARD *b, int k)
{
  if (b->board[k-11] == BKING || b->board[k-10] == BKING ||
      b->board[k-9]  == BKING || b->board[k-1]  == BKING ||
      b->board[k+1]  == BKING || b->board[k+9]  == BKING ||
      b->board[k+10] == BKING || b->board[k+11] == BKING) {
    return 1;
  }
  return 0;
}

/* Test Black Diagonal Attack */

static inline int bdattacks(BOARD *b, int k)
{
  int kk;

  kk = k; do {
    kk -= 11;
  } while (b->board[kk] == EMPTY);
  if ((b->board[kk] & BDIAG) == BDIAG) return 1;

  kk = k; do {
    kk -= 9;
  } while (b->board[kk] == EMPTY);
  if ((b->board[kk] & BDIAG) == BDIAG) return 1;

  kk = k; do {
    kk += 9;
  } while (b->board[kk] == EMPTY);
  if ((b->board[kk] & BDIAG) == BDIAG) return 1;

  kk = k; do {
    kk += 11;
  } while (b->board[kk] == EMPTY);
  if ((b->board[kk] & BDIAG) == BDIAG) return 1;

  return 0;
}

/* Test Black Straight Attack */

static inline int bsattacks(BOARD *b, int k)
{
  int kk;

  kk = k; do {
    kk -= 10;
  } while (b->board[kk] == EMPTY);
  if ((b->board[kk] & BSTRT) == BSTRT) return 1;

  kk = k; do {
    kk -= 1;
  } while (b->board[kk] == EMPTY);
  if ((b->board[kk] & BSTRT) == BSTRT) return 1;

  kk = k; do {
    kk += 1;
  } while (b->board[kk] == EMPTY);
  if ((b->board[kk] & BSTRT) == BSTRT) return 1;

  kk = k; do {
    kk += 10;
  } while (b->board[kk] == EMPTY);
  if ((b->board[kk] & BSTRT) == BSTRT) return 1;

  return 0;
}

/* Test Black Attack (excluding en passant captures) */

static inline int battacks(BOARD *b, int k)
{
  return (bpattacks(b, k) || bhattacks(b, k) || bkattacks(b, k) ||
                             bdattacks(b, k) || bsattacks(b, k));
}

/* Test Check */

static inline int inCheck(BOARD *b)
{
  if (STATE_wtm(b->state)) {
    assert(b->board[b->wk] == WKING);
    return battacks(b, b->wk);
  }
  else {
    assert(b->board[b->bk] == BKING);
    return wattacks(b, b->bk);
  }
}

/************************
 **** Move Utilities ****
 ************************/

/* Dump Notational Move (LOW) */

static void showMov(FILE *myfile, BOARD *b, uint32 mov)
{
  static char trans[] = { ' ', '?', '?', '?', '?', '?', '?', '?',
                          '?', '?', '?', '?', '?', '?', '?', '?',
                          ' ', 'N', 'B', '?', 'R', '?', 'Q', '?',
                          'K', '?', '?', '?', '?', '?', '?', '?',
                          ' ', 'N', 'B', '?', 'R', '?', 'Q', '?',
                          'K', '?', '?', '?', '?', '?', '?', '?'  };

  int f  = (mov & FROM );
  int t  = (mov & TO   ) >> 8;
  int p  = (mov & PROMO) >> 16;

  int fx = placex[f], fy = placey[f];
  int tx = placex[t], ty = placey[t];

  if (mov & CASTLE) {
    if (t == 27 || t == 97) {
      fprintf(myfile, " 0-0    ");
    }
    else if (t == 23 || t == 93) {
      fprintf(myfile, " 0-0-0  ");
    }
    else {
      fprintf(myfile, " ?-?    ");
    }
  }
  else if (mov & ENPASS) {
    fprintf(myfile, " %c%dx%c%dep", 'a'+fx, fy+1, 'a'+tx, ty+1);
  }
  else {
    char mt = (b->board[t] != EMPTY) ? 'x' : '-';
    fprintf(myfile, "%c%c%d%c%c%d%c ", trans[b->board[f]], 'a'+fx, fy+1, mt, 'a'+tx, ty+1, trans[p]);
  }
  fputc((mov & CHECK) ? '+' : ' ', myfile);
}

/* Apply Move */

static uint32 applyMov(BOARD *b, uint32 mov, int fast)
{
  int f = (mov & FROM );
  int t = (mov & TO   ) >> 8;
  int r = 0;

  uint64 nz = b->zobrist;

  /* update board */
  if (mov & CASTLE) {
    assert((f == 25 && (t == 23 || t == 27)) ||
           (f == 95 && (t == 93 || t == 97)));
    if (t == 23) {
      assert(b->board[21] == WROOK && b->board[22] == EMPTY &&
             b->board[23] == EMPTY && b->board[24] == EMPTY && b->board[25] == WKING);
      b->board[21] = EMPTY; b->board[23] = WKING;
      b->board[24] = WROOK; b->board[25] = EMPTY;
      b->wk = 23;
      if (!fast) {
        nz ^= ZOB(25,WKING)^ZOB(23,WKING)^ZOB(21,WROOK)^ZOB(24,WROOK);
        auxDel(b, 0, 21); auxDel(b, 0, 25); auxAdd(b, 0, 23); auxAdd(b, 0, 24);
      }
    }
    else if (t == 27) {
      assert(b->board[25] == WKING && b->board[26] == EMPTY &&
             b->board[27] == EMPTY && b->board[28] == WROOK);
      b->board[25] = EMPTY; b->board[26] = WROOK; 
      b->board[27] = WKING; b->board[28] = EMPTY;
      b->wk = 27;
      if (!fast) {
        nz ^= ZOB(25,WKING)^ZOB(27,WKING)^ZOB(28,WROOK)^ZOB(26,WROOK);
        auxDel(b, 0, 25); auxDel(b, 0, 28); auxAdd(b, 0, 26); auxAdd(b, 0, 27);
      }
    }
    else if (t == 93) {
      assert(b->board[91] == BROOK && b->board[92] == EMPTY &&
             b->board[93] == EMPTY && b->board[94] == EMPTY && b->board[95] == BKING);
      b->board[91] = EMPTY; b->board[93] = BKING; 
      b->board[94] = BROOK; b->board[95] = EMPTY;
      b->bk = 93;
      if (!fast) {
        nz ^= ZOB(95,BKING)^ZOB(93,BKING)^ZOB(91,BROOK)^ZOB(94,BROOK);
        auxDel(b, 1, 91); auxDel(b, 1, 95); auxAdd(b, 1, 93); auxAdd(b, 1, 94);
      }
    }
    else {
      assert(b->board[95] == BKING && b->board[96] == EMPTY &&
             b->board[97] == EMPTY && b->board[98] == BROOK);
      b->board[95] = EMPTY; b->board[96] = BROOK; 
      b->board[97] = BKING; b->board[98] = EMPTY;
      b->bk = 97;
      if (!fast) {
        nz ^= ZOB(95,BKING)^ZOB(97,BKING)^ZOB(98,BROOK)^ZOB(96,BROOK);
        auxDel(b, 1, 95); auxDel(b, 1, 98); auxAdd(b, 1, 96); auxAdd(b, 1, 97);
      }
    }
  }
  else if (mov & ENPASS) {
    assert((41 <= t && t <= 48) || (71 <= t && t <= 78));
    b->board[t] = b->board[f];
    b->board[f] = EMPTY;
    if (t <= 48) {
      assert(b->board[t+10] == WPAWN);
      mov |= (WPAWN << 24);
      b->board[t+10] = EMPTY; /* sic! */
      if (!fast) {
        nz ^= ZOB(f,BPAWN)^ZOB(t,BPAWN)^ZOB(t+10,WPAWN);
        auxDel(b, 0, t+10); auxDel(b, 1, f); auxAdd(b, 1, t);
      }
    }
    else {
      assert(b->board[t-10] == BPAWN);
      mov |= (BPAWN << 24);
      b->board[t-10] = EMPTY; /* sic! */
      if (!fast) {
        nz ^= ZOB(f,WPAWN)^ZOB(t,WPAWN)^ZOB(t-10,BPAWN);
        auxDel(b, 1, t-10); auxDel(b, 0, f); auxAdd(b, 0, t);
      }
    }
    r = 1;
  }
  else {
    int p = (mov & PROMO) >> 16;
    int o = b->board[f];
    int q = b->board[t];
    int g = (p == EMPTY) ? o : p; /* promotion? */
    if (q != EMPTY) {
      r = 1;
      mov |= (q << 24);
      if (!fast) {
        int c = STATE_wtm(b->state) ? 1 : 0;
        nz ^= ZOB(t,q);
        auxDel(b, c, t);
      }
    }
    else if (o == WPAWN || o == BPAWN) {
      r = 1;
    }
    b->board[t] = g;
    b->board[f] = EMPTY;
    if      (o == WKING) b->wk = t;
    else if (o == BKING) b->bk = t;
    if (!fast) {
      int c = STATE_wtm(b->state) ? 0 : 1;
      nz ^= ZOB(f,o)^ZOB(t,g);
      auxDel(b, c, f);
      auxAdd(b, c, t);
    }
  }

  if (fast) {
    /* set the check flag based on the original side-to-move state
     * (note that we could avoid this computation in case the move
     *  is invalid due to in-check, but prototype code to avoid this
     *  did not yield substantial enough savings)
     */
    if (STATE_wtm(b->state)) { 
      if (wattacks(b, b->bk)) mov |= CHECK;
    }
    else {
      if (battacks(b, b->wk)) mov |= CHECK;
    }
    goto fastend;
  }

  /* update state */

  recPos(b);
  if (r) {
    b->r50cnt = 0;
  }
  else {
    b->r50cnt++;
  }

  b->zobrist = (nz^zobrist2);

  STATE_NEW_MOV(b->state);
  
  if (b->board[t] == WPAWN) {
    if (f <= 38 && 51 <= t) {
      assert(f-31 == placex[f]);
      STATE_SET_ENP(b->state, f-31);
    }
  }
  else if (b->board[t] == BPAWN) {
    if (81 <= f && t <= 68) {
      assert(f-81 == placex[f]);
      STATE_SET_ENP(b->state, f-81);
    }
  }
  else if (b->state & 0x00f0) {
    if      (f == 25) STATE_CLR_WC2(b->state);
    else if (f == 95) STATE_CLR_BC2(b->state);
    else if (f == 21) STATE_CLR_WCQ(b->state);
    else if (f == 28) STATE_CLR_WCK(b->state);
    else if (f == 91) STATE_CLR_BCQ(b->state);
    else if (f == 98) STATE_CLR_BCK(b->state);
  }

  assert(b->zobrist == compZobrist(b));

fastend:
  return mov;
}

/* Undo Move */

static void takebMov(BOARD *b, uint32 mov, uint32 os, uint32 op, uint32 o5, uint64 oz, int fast)
{
  int f = (mov & FROM );
  int t = (mov & TO   ) >> 8;

  if (!fast) {
    b->state   = os;
    b->plycnt  = op;
    b->r50cnt  = o5;
    b->zobrist = oz;
  }
  
  /* update board */ 
  if (mov & CASTLE) {  
    assert((f == 25 && (t == 23 || t == 27)) || 
           (f == 95 && (t == 93 || t == 97)));
    if (t == 23) {
      assert(b->board[23] == WKING && b->board[24] == WROOK);
      b->board[21] = WROOK; b->board[23] = EMPTY; 
      b->board[24] = EMPTY; b->board[25] = WKING;
      b->wk = 25;
      if (!fast) {
        auxDel(b, 0, 23); auxDel(b, 0, 24); auxAdd(b, 0, 21); auxAdd(b, 0, 25);
      }
    }
    else if (t == 27) {
      assert(b->board[26] == WROOK && b->board[27] == WKING);
      b->board[25] = WKING; b->board[26] = EMPTY; 
      b->board[27] = EMPTY; b->board[28] = WROOK;
      b->wk = 25;
      if (!fast) {
        auxDel(b, 0, 26); auxDel(b, 0, 27); auxAdd(b, 0, 25); auxAdd(b, 0, 28);
      }
    }
    else if (t == 93) {
      assert(b->board[93] == BKING && b->board[94] == BROOK);
      b->board[91] = BROOK; b->board[93] = EMPTY; 
      b->board[94] = EMPTY; b->board[95] = BKING;
      b->bk = 95;
      if (!fast) {
        auxDel(b, 1, 93); auxDel(b, 1, 94); auxAdd(b, 1, 91); auxAdd(b, 1, 95);
      }
    }
    else {
      assert(b->board[96] == BROOK && b->board[97] == BKING);
      b->board[95] = BKING; b->board[96] = EMPTY; 
      b->board[97] = EMPTY; b->board[98] = BROOK;
      b->bk = 95;
      if (!fast) {
        auxDel(b, 1, 96); auxDel(b, 1, 97); auxAdd(b, 1, 95); auxAdd(b, 1, 98);
      }
    }
  }
  else if (mov & ENPASS) {
    assert((41 <= t && t <= 48) || (71 <= t && t <= 78));
    b->board[f] = b->board[t];
    b->board[t] = EMPTY;
    if (t <= 48) {
      assert((mov & CAP) >> 24 == WPAWN);
      b->board[t+10] = WPAWN; /* sic! */
      if (!fast) {
        auxDel(b, 1, t); auxAdd(b, 1, f); auxAdd(b, 0, t+10);
      }
    }
    else {
      assert((mov & CAP) >> 24 == BPAWN);
      b->board[t-10] = BPAWN; /* sic! */
      if (!fast) {
        auxDel(b, 0, t); auxAdd(b, 0, f); auxAdd(b, 1, t-10);
      }
    }
  }
  else {
    int o;
    int p = (mov & PROMO) >> 16;
    if (p == EMPTY) {
      o = b->board[t];
      if      (o == WKING) { b->wk = f; }
      else if (o == BKING) { b->bk = f; }
    }
    else {
      assert(t <= 28 || 91 <= t);
      o = (t <= 28) ? BPAWN : WPAWN;
    }
    b->board[f] = o;
    b->board[t] = (mov & CAP) >> 24;
    if (!fast) {
      int c = STATE_wtm(b->state) ? 0 : 1;
      auxDel(b, c, t);
      auxAdd(b, c, f);
      if (mov & CAP) auxAdd(b, 1-c, t);
    }
  }
}

/* MVV/LVA (MMV sorts, LVA breaks ties) */

static inline int mvv_lva(BOARD *b, uint32 mi, uint32 mj)
{
  uint32 g1 = mi & CAP;
  uint32 g2 = mj & CAP;
  assert(g1 && g2);
  if (g1 > g2) {
    return 1;
  }
  else if (g1 == g2) {
    uint32 p1 = (b->board[(mi & FROM)]);
    uint32 p2 = (b->board[(mj & FROM)]);
    if (p1 < p2) {
      return 1;
    }
  }
  return 0;
}

/* Good capture */

static inline int good_cap(BOARD *b, uint32 mi)
{
  if (mi & CAP) {
    static int cap_val[] = { 1, 3, 3, 3, 5, 5, 10 };
    uint32 g = (mi >> 24);
    uint32 p = (b->board[(mi & FROM)]);
    /* compare piece value
     * (map king to pawn, cannot be recaptured!)
     */
    if (cap_val[g & 0x07] > cap_val[p & 0x07]) return 1;
  }
  return 0;
}

/* Generate all Moves */

#define wadd(t,p) { moves[m] = applyMov(b, ((k)|(S08(t))|((p)<<16)), 1);   \
                    ic = battacks(b, b->wk);                               \
                    takebMov(b, moves[m], 0, 0, 0, 0, 1);                  \
                    if (!ic) m++;                                          \
                  }

#define badd(t,p) { moves[m] = applyMov(b, ((k)|(S08(t))|((p)<<16)), 1);   \
                    ic = wattacks(b, b->bk);                               \
                    takebMov(b, moves[m], 0, 0, 0, 0, 1);                  \
                    if (!ic) m++;                                          \
                  }

#define wgadd(t)   { wadd((t),EMPTY)                           }
#define bgadd(t)   { badd((t),EMPTY)                           }
#define weadd(t)   { if (!is_whiteI(b->board[(t)])) wgadd((t)) }
#define beadd(t)   { if (!is_blackI(b->board[(t)])) bgadd((t)) }

static int lastcap;
static int lastcheck;

static int genmoves(BOARD *b, uint32 *sorted, uint32 dp, int sortmv)
{
  MOVES moves_gen;

  uint32 *moves = (sortmv) ? moves_gen : sorted;

  int q, k, kk, m = 0, ic, i, j;

  if (STATE_wtm(b->state)) {
    uint32 *qm = b->auxB;
    int p = b->auxw;
    for (q = 0; q < p; q++) { /* REAL SPARSE */
      k = qm[q];
      assert(b->board[k] & WHITE);
      switch (b->board[k]) {
        case WKING:
          assert(b->wk == k);
          weadd(k-11); weadd(k-10); weadd(k-9);  weadd(k-1);
          weadd(k+1);  weadd(k+9);  weadd(k+10); weadd(k+11);
          /* castling */
          if (k == 25) {
            if (STATE_wck(b->state)   && 
                b->board[26] == EMPTY &&
                b->board[27] == EMPTY &&
                b->board[28] == WROOK && !battacks(b, 25) &&
                                         !battacks(b, 26) &&
                                         !battacks(b, 27)) {
              wadd(27,CASTLE>>16);
            }
            if (STATE_wcq(b->state)   && 
                b->board[21] == WROOK &&
                b->board[22] == EMPTY &&
                b->board[23] == EMPTY &&
                b->board[24] == EMPTY && !battacks(b, 23) &&
                                         !battacks(b, 24) &&
                                         !battacks(b, 25)) {
              wadd(23,CASTLE>>16);
            }
          }
          break;  
        case WKNIGHT:            
          weadd(k-21); weadd(k-19); weadd(k-12); weadd(k-8); 
          weadd(k+8);  weadd(k+12); weadd(k+19); weadd(k+21); 
          break;
        case WPAWN:
          assert(k <= 88);
          if (b->board[k+10] == EMPTY) {
            if (k <= 78) {
              wgadd(k+10);
              if (k <= 38 && b->board[k+20] == EMPTY) {
                wgadd(k+20);
              }
            }
            else { /* move promotions */
              wadd(k+10,WKNIGHT);
              wadd(k+10,WBISHOP);
              wadd(k+10,WROOK);
              wadd(k+10,WQUEEN);
            }
          }
          for (kk = k+9; kk <= k+11; kk += 2) {
            if (is_blackE(b->board[kk])) {
              if (k <= 78) {
                wgadd(kk);
              }
              else { /* capture promotions */
                wadd(kk,WKNIGHT);
                wadd(kk,WBISHOP);
                wadd(kk,WROOK);
                wadd(kk,WQUEEN);              
              }
            }
          }
          if (62 <= k && k <= 68 && k-62 == STATE_enp(b->state)) {
            wadd(k+9, ENPASS>>16);
          }
          else if (61 <= k && k <= 67 && k-60 == STATE_enp(b->state)) {
            wadd(k+11,ENPASS>>16);
          }
          break;
        case WQUEEN:
          kk = k;
          do {
            kk -= 11; 
            if (is_whiteI(b->board[kk])) break;
            wgadd(kk);
          } while (b->board[kk] == EMPTY);
          kk = k;
          do {
            kk -= 9; 
            if (is_whiteI(b->board[kk])) break;
            wgadd(kk);
          } while (b->board[kk] == EMPTY);
          kk = k;
          do {
            kk += 9; 
            if (is_whiteI(b->board[kk])) break;
            wgadd(kk);
          } while (b->board[kk] == EMPTY);
          kk = k;
          do {
            kk += 11; 
            if (is_whiteI(b->board[kk])) break;
            wgadd(kk);
          } while (b->board[kk] == EMPTY);
          /* FALL INTO ROOK MOVES */
        case WROOK:
          kk = k;
          do {
            kk -= 10; 
            if (is_whiteI(b->board[kk])) break;
            wgadd(kk);
          } while (b->board[kk] == EMPTY);
          kk = k;
          do {
            kk -= 1; 
            if (is_whiteI(b->board[kk])) break;
            wgadd(kk);
          } while (b->board[kk] == EMPTY);
          kk = k;
          do {
            kk += 1; 
            if (is_whiteI(b->board[kk])) break;
            wgadd(kk);
          } while (b->board[kk] == EMPTY);
          kk = k;
          do {
            kk += 10; 
            if (is_whiteI(b->board[kk])) break;
            wgadd(kk);
          } while (b->board[kk] == EMPTY);
          break;
        case WBISHOP:
          kk = k;
          do {
            kk -= 11; 
            if (is_whiteI(b->board[kk])) break;
            wgadd(kk);
          } while (b->board[kk] == EMPTY);
          kk = k;
          do {
            kk -= 9; 
            if (is_whiteI(b->board[kk])) break;
            wgadd(kk);
          } while (b->board[kk] == EMPTY);
          kk = k;
          do {
            kk += 9; 
            if (is_whiteI(b->board[kk])) break;
            wgadd(kk);
          } while (b->board[kk] == EMPTY);
          kk = k;
          do {
            kk += 11; 
            if (is_whiteI(b->board[kk])) break;
            wgadd(kk);
          } while (b->board[kk] == EMPTY);
          break;
      } /* switch */
    }
  }
  else {
    uint32 *qm = b->auxB + 16;
    int p = b->auxb;
    for (q = 0; q < p; q++) { /* REAL SPARSE */
      k = qm[q];
      assert(b->board[k] & BLACK);
      switch (b->board[k]) {
        case BKING:
          assert(b->bk == k);
          beadd(k-11); beadd(k-10); beadd(k-9);  beadd(k-1);
          beadd(k+1);  beadd(k+9);  beadd(k+10); beadd(k+11);
          /* castling */
          if (k == 95) {
            if (STATE_bck(b->state)   && 
                b->board[96] == EMPTY && 
                b->board[97] == EMPTY && 
                b->board[98] == BROOK && !wattacks(b, 95) &&
                                         !wattacks(b, 96) &&
                                         !wattacks(b, 97)) {
              badd(97,CASTLE>>16);
            }
            if (STATE_bcq(b->state)   && 
                b->board[91] == BROOK &&
                b->board[92] == EMPTY &&
                b->board[93] == EMPTY &&
                b->board[94] == EMPTY && !wattacks(b, 93) &&
                                         !wattacks(b, 94) &&
                                         !wattacks(b, 95)) {
              badd(93,CASTLE>>16);
            }
          }
          break;  
        case BKNIGHT:            
          beadd(k-21); beadd(k-19); beadd(k-12); beadd(k-8); 
          beadd(k+8);  beadd(k+12); beadd(k+19); beadd(k+21); 
          break;
        case BPAWN:
          assert(31 <= k);
          if (b->board[k-10] == EMPTY) {
            if (41 <= k) {
              bgadd(k-10);
              if (81 <= k && b->board[k-20] == EMPTY) {
                bgadd(k-20);
              }
            }
            else { /* move promotions */
              badd(k-10,BKNIGHT);
              badd(k-10,BBISHOP);
              badd(k-10,BROOK);
              badd(k-10,BQUEEN);              
            }
          }
          for (kk = k-11; kk <= k-9; kk += 2) {
            if (is_whiteE(b->board[kk])) {
              if (41 <= k) {
                bgadd(kk);
              }
              else { /* capture promotions */
                badd(kk,BKNIGHT);
                badd(kk,BBISHOP);
                badd(kk,BROOK);
                badd(kk,BQUEEN);                
              }
            }
          }
          if (52 <= k && k <= 58 && k-52 == STATE_enp(b->state)) {
            badd(k-11,ENPASS>>16);
          }
          else if (51 <= k && k <= 57 && k-50 == STATE_enp(b->state)) {
            badd(k-9, ENPASS>>16);
          }
          break;
        case BQUEEN:
          kk = k;
          do {
            kk -= 11; 
            if (is_blackI(b->board[kk])) break;
            bgadd(kk);
          } while (b->board[kk] == EMPTY);
          kk = k;
          do {
            kk -= 9; 
            if (is_blackI(b->board[kk])) break;
            bgadd(kk);
          } while (b->board[kk] == EMPTY);
          kk = k;
          do {
            kk += 9; 
            if (is_blackI(b->board[kk])) break;
            bgadd(kk);
          } while (b->board[kk] == EMPTY);
          kk = k;
          do {
            kk += 11; 
            if (is_blackI(b->board[kk])) break;
            bgadd(kk);
          } while (b->board[kk] == EMPTY);
          /* FALL INTO ROOK MOVES */
        case BROOK:
          kk = k;
          do {
            kk -= 10; 
            if (is_blackI(b->board[kk])) break;
            bgadd(kk);
          } while (b->board[kk] == EMPTY);
          kk = k;
          do {
            kk -= 1; 
            if (is_blackI(b->board[kk])) break;
            bgadd(kk);
          } while (b->board[kk] == EMPTY);
          kk = k;
          do {
            kk += 1; 
            if (is_blackI(b->board[kk])) break;
            bgadd(kk);
          } while (b->board[kk] == EMPTY);
          kk = k;
          do {
            kk += 10; 
            if (is_blackI(b->board[kk])) break;
            bgadd(kk);
          } while (b->board[kk] == EMPTY);
          break;
        case BBISHOP:
          kk = k;
          do {
            kk -= 11; 
            if (is_blackI(b->board[kk])) break;
            bgadd(kk);
          } while (b->board[kk] == EMPTY);
          kk = k;
          do {
            kk -= 9; 
            if (is_blackI(b->board[kk])) break;
            bgadd(kk);
          } while (b->board[kk] == EMPTY);
          kk = k;
          do {
            kk += 9; 
            if (is_blackI(b->board[kk])) break;
            bgadd(kk);
          } while (b->board[kk] == EMPTY);
          kk = k;
          do {
            kk += 11; 
            if (is_blackI(b->board[kk])) break;
            bgadd(kk);
          } while (b->board[kk] == EMPTY);
          break;
      } /* switch */
    }
  }

  /* cheap move ordering */

  if (sortmv) {
    int kc = 0, pc = 0, cc = 0, tc = 0, mc = 0;
    uint32 km = (dp < MAXDP) ? killerm[dp] : 0;
    /* setup counters */
    for (i = 0; i < m; i++) {
      uint32 mi = moves[i];
      if      (mi == km)   kc++;
      else if (mi & PROMO) pc++;
      else if (mi & CAP)   cc++;
      else if (mi & CHECK) tc++;
#ifndef NDEBUG
      else mc++;
#endif
    }
    /* fill */
    assert(kc <= 1);
    pc += kc;
    cc += pc;
    tc += cc;
    assert(tc + mc == m);
    mc = m;
    for (i = 0; i < m; i++) {
      uint32 mi = moves[i];
      if      (mi == km)   sorted[0]    = mi;
      else if (mi & PROMO) sorted[--pc] = mi;
      else if (mi & CAP)   sorted[--cc] = mi;
      else if (mi & CHECK) sorted[--tc] = mi;
      else                 sorted[--mc] = mi;
    }
    /* partially sort captures with MMV/LVA */
    for (j = cc; j <= cc+2; j++) {
      int stable = 1;
      for (i = tc-1; i > j; i--) {
        uint32 mi = sorted[i];
        if (mvv_lva(b, mi, sorted[i-1])) {
          sorted[i] = sorted[i-1]; sorted[i-1] = mi;
          stable = 0;
        }
      }  /* for i */
      if (stable) break;
    }  /* for j */
    /* set "good" move range */
    lastcap = tc;
    lastcheck = mc;
  }

  return m;
}

/**********************
 **** Chess Engine ****
 **********************/

/* Straight Behind Rule */

static inline int isBehind(BOARD *b, int k, int p, uint32 xx, uint32 yy)
{
  while (1) {
    k += p;
    if ((b->board[k] & xx) == xx) return  15;
    if ((b->board[k] & yy) == yy) return -15;
    if ((b->board[k] != EMPTY))   return  0;
  }
}

/* Closer Distance */

static inline int gClose(int w, int b)
{
  int h1 = placex[b] - placex[w];
  int h2 = placey[b] - placey[w];
  if (h1 < 0) h1 = -h1;
  if (h2 < 0) h2 = -h2;
  return (7 - ((h1 > h2) ? h1 : h2));
}

/* Open Line */

static inline int openLine(int k, uint32 ps1, uint32 ps2, uint32 okb)
{
  uint32 bit = (1u << placex[k]);
  if (!(ps1 & bit)) {
    if (!(ps2 & bit)) return (okb & bit) ? 20 : 12;
    return (okb & bit) ? 10 : 6;
  }
  return 0;
}

/* Score Bishop */

static inline int scoreBishop(BOARD *b, int k, int ok, int fl, int fr, uint32 xx)
{
  int score = placeminor[k] + gClose(k, ok);
  /* do not block forward with own pawns */
  if (b->board[k + fl] != xx) score += 2;
  if (b->board[k + fr] != xx) score += 2;
  return score;
}

/* Bad Bishop */

static inline int badBishop(BOARD *b, int k, uint32 xx) {
  int score = 0;
  if (colorb[k] == 1) {
    if (b->board[54] == xx) score -= 10;
    if (b->board[65] == xx) score -= 10;
    if (b->board[63] == xx) score -= 9;
    if (b->board[56] == xx) score -= 9;
    if (b->board[43] == xx) score -= 8;
    if (b->board[45] == xx) score -= 8;
    if (b->board[74] == xx) score -= 8;
    if (b->board[76] == xx) score -= 8;
  }
  else {
    if (b->board[55] == xx) score -= 10;
    if (b->board[64] == xx) score -= 10;    
    if (b->board[53] == xx) score -= 9;
    if (b->board[66] == xx) score -= 9;
    if (b->board[44] == xx) score -= 8;
    if (b->board[46] == xx) score -= 8;
    if (b->board[73] == xx) score -= 8;
    if (b->board[75] == xx) score -= 8;
  } 
  return score;
}

/* Score Knight */

static inline int scoreKnight(BOARD *b, int k, int ok,
                                               int z0, int z1, int z2,
                                               int bl, int br, uint32 xx)
{
  int score = placeminor[k] + gClose(k, ok);
  /* bad knights on first rank,
   * advanced knights support point on sixth or fifth rank
   */
  if (placey[k] == z0) {
    score -= 9;
  }
  else if (placey[k] == z1) {
    if (b->board[k + bl] == xx) score += 6;
    if (b->board[k + br] == xx) score += 6;
  }
  else if (placey[k] == z2) {
    if (b->board[k + bl] == xx) score += 3;
    if (b->board[k + br] == xx) score += 3;
  }
  return score;
}

/* Evaluation Function */

static int evalFunc(BOARD *b, uint32 dp)
{
  uint32 *qm;

  int score = 0, piece = 0, k, q, qt;

  int wk = b->wk, wq = 0;
  int bk = b->bk, bq = 0;

  int wr1 = 0, wr2 = 0;
  int br1 = 0, br2 = 0;

  int wb1 = 0, wb2 = 0;
  int bb1 = 0, bb2 = 0;

  int wn1 = 0, wn2 = 0;
  int bn1 = 0, bn2 = 0;

  uint32 wps = 0, wkb;
  uint32 bps = 0, bkb;

  if (dp > seldp) seldp = dp;

  /* board analysis and material analysis */
  piece = b->auxw + b->auxb;
  qm = b->auxB;
  qt = b->auxw;
  for (q = 0; q < qt; q++) { /* REAL SPARSE */
    k = qm[q];
    switch (b->board[k]) {
      /***************** white score *****************************/
      case WKING:   assert(wk == k);
                    break;
      case WQUEEN:  score += 900;
                    wq = k;
                    break;
      case WROOK:   score += 500;
                    if (wr1) wr2 = k; else wr1 = k;
                    break;
      case WBISHOP: score += 301;
                    if (wb1) wb2 = k; else wb1 = k;
                    break;
      case WKNIGHT: score += 300;
                    if (wn1) wn2 = k; else wn1 = k;
                    break;
      case WPAWN:   score += 98;
                    wps |= (1u << placex[k]);
                    /* award right-connectivity */
                    if (b->board[k-9]  == WPAWN ||
                        b->board[k+1]  == WPAWN ||
                        b->board[k+11] == WPAWN) score++;
                    /* simple passed pawn rewards */
                    switch (placey[k]) {
                      case 6:
                        score += (55 + isBehind(b, k, -10, WSTRT, BSTRT));
                        if (b->board[k-1]  == WPAWN ||
                            b->board[k-11] == WPAWN) score += 14;
                        if (b->board[k+1]  == WPAWN ||
                            b->board[k-9]  == WPAWN) score += 14;
                        break;
                      case 5: 
                        if (b->board[k+9]  != BPAWN &&
                            b->board[k+10] != BPAWN &&
                            b->board[k+11] != BPAWN) {
                          score += (34 + isBehind(b, k, -10, WSTRT, BSTRT));
                        }
                        break;             
                      case 4:
                        if (b->board[k+9]  != BPAWN &&
                            b->board[k+19] != BPAWN &&
                            b->board[k+10] != BPAWN &&
                            b->board[k+20] != BPAWN &&
                            b->board[k+11] != BPAWN &&
                            b->board[k+21] != BPAWN) {
                          score += (23 + isBehind(b, k, -10, WSTRT, BSTRT));
                        }
                        break;
                    } /* switch */
                    break;
      default:      assert(0);
    } /* switch */
  }
  qm = b->auxB + 16;
  qt = b->auxb;
  for (q = 0; q < qt; q++) { /* REAL SPARSE */
    k = qm[q];
    switch (b->board[k]) {
      /***************** black score *****************************/
      case BKING:   assert(bk == k);
                    break;
      case BQUEEN:  score -= 900;
                    bq = k;
                    break;
      case BROOK:   score -= 500;
                    if (br1) br2 = k; else br1 = k;
                    break;
      case BBISHOP: score -= 301;
                    if (bb1) bb2 = k; else bb1 = k;
                    break;
      case BKNIGHT: score -= 300;
                    if (bn1) bn2 = k; else bn1 = k;
                    break;
      case BPAWN:   score -= 98;
                    bps |= (1u << placex[k]);                    
                    /* award right-connectivity */
                    if (b->board[k-9]  == BPAWN ||
                        b->board[k+1]  == BPAWN ||
                        b->board[k+11] == BPAWN) score--;
                    /* simple passed pawn rewards */
                    switch (placey[k]) {
                      case 1:
                        score -= (55 + isBehind(b, k, 10, BSTRT, WSTRT));
                        if (b->board[k-1]  == BPAWN ||
                            b->board[k+9]  == BPAWN) score -= 14;
                        if (b->board[k+1]  == BPAWN ||
                            b->board[k+11] == BPAWN) score -= 14;  
                        break;
                      case 2:
                        if (b->board[k-11] != WPAWN &&
                            b->board[k-10] != WPAWN &&
                            b->board[k-9]  != WPAWN) {
                          score -= (34 + isBehind(b, k, 10, BSTRT, WSTRT));
                        }
                        break;
                      case 3:
                        if (b->board[k-11] != WPAWN &&
                            b->board[k-21] != WPAWN &&
                            b->board[k-10] != WPAWN &&
                            b->board[k-20] != WPAWN &&
                            b->board[k-19] != WPAWN &&
                            b->board[k-9]  != WPAWN) {
                          score -= (23 + isBehind(b, k, 10, BSTRT, WSTRT));
                        }
                        break;
                    } /* switch */
                    break;
      default:      assert(0);
    } /* switch */
  }

  /* positional analysis */
  if (5 < piece) {
    /* pawn structure */
    score += (pawnval[wps] - pawnval[bps]);
    /* bishop pair advantage */
    if      (wb2 && !bb2) score += 6;
    else if (bb2 && !wb2) score -= 6;
    /* white minor placement */
    if (wb1) {
      score += scoreBishop(b, wb1, bk, 9, 11, WPAWN);
      if (wb2) score += scoreBishop(b, wb2, bk, 9, 11, WPAWN);
      else score += badBishop(b, wb1, WPAWN);
    }
    if (wn1) {
      score += scoreKnight(b, wn1, bk, 0, 6, 5, -11, -9, WPAWN);
      if (wn2) score += scoreKnight(b, wn2, bk, 0, 6, 5, -11, -9, WPAWN);
    }
    /* black minor placement */
    if (bb1) {
      score -= scoreBishop(b, bb1, wk, -11, -9, BPAWN);
      if (bb2) score -= scoreBishop(b, bb2, wk, -11, -9, BPAWN);
      else score -= badBishop(b, bb1, BPAWN);
    }
    if (bn1) {
      score -= scoreKnight(b, bn1, wk, 7, 3, 4, 9, 11, BPAWN);
      if (bn2) score -= scoreKnight(b, bn2, wk, 7, 3, 4, 9, 11, BPAWN);
    }
    /* open lines, rook batteries, 7th rank rooks */
    wkb = leftmidright[placex[wk]];
    bkb = leftmidright[placex[bk]];
    if (wq) score += (openLine(wq, wps, bps, bkb) + gClose(wq, bk));
    if (bq) score -= (openLine(bq, bps, wps, wkb) + gClose(bq, wk));
    if (wr1) {
      score += (openLine(wr1, wps, bps, bkb) + gClose(wr1, bk));
      if (wr2) {
        score += (openLine(wr2, wps, bps, bkb) + gClose(wr2, bk));;
        if (placex[wr1] == placex[wr2]) score += 4;
        if (placey[wr1] == 6 &&
            placey[wr2] == 6) score += 5;
      }
    }
    if (br1) {
      score -= (openLine(br1, bps, wps, wkb) + gClose(br1, wk));
      if (br2) {
        score -= (openLine(br2, bps, wps, wkb) + gClose(br2, wk));
        if (placex[br1] == placex[br2]) score -= 4;
        if (placey[br1] == 1 &&
            placey[br2] == 1) score -= 5;
      }
    }
    /* late and early rules */
    if (piece <= 18) {
      /* develop kings if no queen threat */
      if (!bq) score += placeminor[wk];
      if (!wq) score -= placeminor[bk];
    }
    else if (piece >= 24) {
      /* center pawns */
      if      (b->board[54] == WPAWN) score += 6;
      else if (b->board[54] == BPAWN) score -= 4;
      if      (b->board[55] == WPAWN) score += 6;
      else if (b->board[55] == BPAWN) score -= 4;
      if      (b->board[64] == WPAWN) score += 4;
      else if (b->board[64] == BPAWN) score -= 6;
      if      (b->board[65] == WPAWN) score += 4;
      else if (b->board[65] == BPAWN) score -= 6; 
      /* award castling */
      if ((wk == 27 && b->board[28] == EMPTY) || wk == 23) score += 9;
      if ((bk == 97 && b->board[98] == EMPTY) || bk == 93) score -= 9;
      /* keep kings behind */
      if (wk <= 28) score += 5;
      if (bk >= 91) score -= 5;
      /* very simple king safety */
      if (!is_whiteE(b->board[wk+9]))  score -= 10;
      if (!is_whiteE(b->board[wk+10])) score -= 10;
      if (!is_whiteE(b->board[wk+11])) score -= 10;
      if (!is_blackE(b->board[bk-11])) score += 10;
      if (!is_blackE(b->board[bk-10])) score += 10;
      if (!is_blackE(b->board[bk-9]))  score += 10;
      /* keep queens behind */
      if (21 <= wq && wq <= 38) score += 7;
      if (81 <= bq)             score -= 7;
    }
  }
  else { /* very late */
    /* detect draw-flavored situations, search should find the exceptions */
    switch (piece) {
      case 0:
      case 1:
      case 2: 
        return 0; /* 2-kings */
      case 3:
        if (!wq && !bq && !wps && !bps && !wr1 && !br1) {
          return 0; /* 2-kings + 1-minor */
        }
        break;
      case 4:  
        if (wq && bq) {
          return 0; /* 2-king + 2-opposing-queens */
        }
        else if ((wr1 || wb1 || wn1) &&
                 (br1 || bb1 || bn1)) {
          return 0; /* 2-kings + 2-opposing-rook/minor */
        }
        else if (wn2 || bn2) {
          return 0; /* 2-knights cannot mate */
        }
        else if (((wb1 || wn1) && bps) ||
                 ((bb1 || bn1) && wps)) {
          return 0; /* 2-kings + 2-opposing-minor/pawn */
        }
      case 5:
        if (((wr1 || wb1 || wn1) && (bb2 || bn2 || (bb1 && bn1))) ||
            ((br1 || bb1 || bn1) && (wb2 || wn2 || (wb1 && wn1)))) {
          return 0; /* 2-kings + 3-opposing-rook,minor/minors */
        }
        if ((wr1 && (wb1 || wn1) && br1) ||
            (br1 && (bb1 || bn1) && wr1)) {
          return 0; /* 2-kings + 3-rook+minor/rook */
        }
        break;
      default:
        assert(0);
    } /* switch */
  }

  return STATE_wtm(b->state) ? score : -score; /* value wrt side-to-move */
}

/* Leaf Node Evaluation */

static int leafNode(BOARD *b, int alpha, int beta, uint32 dp, uint32 nowinchk)
{
  /* leaf evaluation cut-off or adjust */

  if (!nowinchk) {
    int v = evalFunc(b, dp);
    if (v >= beta) {
      return beta;
    }
    else if (v > alpha) {
      alpha = v; /* not all moves considered! */
    }
    else if (v < alpha - 900) {
      return alpha;
    }
  }

  /* quiescence search */

  if (dp < MAXDP) { /* protect against errors */

    MOVES moves;
    int   m, m1, m2, i, v;

    /* generate moves */
    m = genmoves(b, moves, MAXDP, 1); /* no killers */
    if (m == 0) {
      return (nowinchk) ? -32500+(int)dp : 0;
    }
    else if (nowinchk) {
      m1 = m;
      m2 = m;
    }
    else {
      m1 = lastcap;
      m2 = lastcheck;
    }

    /* inspect selective moves */
    for (i = 0; i < m2; i++) {
      uint32 os = b->state, op = b->plycnt, o5 = b->r50cnt;
      uint64 oz = b->zobrist;
      applyMov(b, moves[i], 0);
      nodes++;
      if (b->r50cnt >= 100 || repPosSloppy(b)) {
        v = 0;
      }
      else if (i < m1) {
        v = - leafNode(b, -beta, -alpha, dp+1, (moves[i] & CHECK));
      }
      else {
        v = alpha;
        if (moves[i] & CHECK) {
          MOVES evades;
          if (genmoves(b, evades, MAXDP, 0) == 0) { /* no killers, no sorting */
            v = 32500-(int)dp;
          }
        }
      }
      takebMov(b, moves[i], os, op, o5, oz, 0);
      /* cut-off or adjust */
      if (v >= beta) {
        return beta;
      }
      else if (v > alpha) {
        alpha = v;
      }
    } /* for all selective moves */

  }

  return alpha;
}

/* NegaMax Search with Alpha-Beta Pruning */

static int searchAB(BOARD *b, int alpha,
                              int beta, uint32 dp,
                                        uint32 dm, uint32 nok, uint32 nowinchk, uint32 ext)
{
  MOVES moves;
  int   m, i, v;

  assert(dp <= dm);
  assert(-32767 <= alpha && alpha <= beta && beta <= 32767);

  nodes++;

  /* claim draw by fifty move rule or threefold repetition? */
  if (b->r50cnt >= 100 || repPosSloppy(b)) {
    return 0;
  }

  if (nowinchk) dm++; /* extend */

  /* tranposition lookup */
#ifdef TRANSON
  v = lookupTrans(b->zobrist, dp, dm, alpha, beta);
  if (v != TRANSNONE) {
    return v;
  }
#endif

  /* search or evaluate */
  if (dp < dm) {

    uint32 pvs = 0;

    /* generate moves */
    m = genmoves(b, moves, dp, 1);
    if (m == 0) {
      return (nowinchk) ? -32500+(int)dp : 0;
    }
    else if (m <= 2) {
      if (dp < extdp) {
        ext = dp + 2;
        dm++; /* tactical extend */
      }
      else if (m == 1) {
        int f = (moves[0] & FROM );
        int t = (moves[0] & TO   ) >> 8;
        if (placeminor[f] >= placeminor[t]) {
          ext = dp + 2;
          dm++; /* tactical extend */
        }
      }
    }
    else if (dp == ext && dp < dm - 1) {
      dm--;
    }

#ifdef NULLMOV
    /* null move
     * NOTE: would like to do this before move generation, but #moves is good
     *       indication of forced situations where null move is dangerous
     */
    if (!nowinchk && 4 <= m && nok) {
      uint32 os = b->state;
      uint32 op = b->plycnt;
      recPos(b);
      STATE_NEW_MOV(b->state);
      b->zobrist ^= zobrist2;
      v = - searchAB(b, -beta, -beta+1, dp + 1, (2 < (dm-dp)) ? dm - 2 : dp + 1, 0, 0, ext);
      b->zobrist ^= zobrist2;
      b->state  = os;
      b->plycnt = op;
      if (v >= beta) {
        return beta;
      }
    }
#endif

    /* inspect moves */
    for (i = 0; i < m; i++) {
      uint32 os = b->state, op = b->plycnt, o5 = b->r50cnt;
      uint64 oz = b->zobrist;
      applyMov(b, moves[i], 0);
      {
        if (pvs) { /* PVS */
          v = - searchAB(b, -alpha-1, -alpha, dp + 1, dm, 1, (moves[i] & CHECK), ext);
          if (alpha < v && v < beta) goto core;
        }
        else { /* CORE */
core:     v = - searchAB(b, -beta, -alpha, dp + 1, dm, 1, (moves[i] & CHECK), ext);
        }
      }
      takebMov(b, moves[i], os, op, o5, oz, 0);
      /* cutt-off or adjust */
      if (v >= beta) {
#ifdef TRANSON
        insertTrans(b->zobrist, dp, dm, TRANSBETA, beta, moves[i]);
#endif
        if (dp < MAXDP) killerm[dp] = moves[i];
        return beta;
      }
      else if (v > alpha) {
        alpha = v;
#ifdef PVS
        pvs = moves[i];
#endif
      }

    } /* for all moves */

#ifdef TRANSON
    insertTrans(b->zobrist, dp, dm, (pvs) ? TRANSEXACT : TRANSALPHA, alpha, pvs);
#endif
    return alpha;
  }
  return leafNode(b, alpha, beta, dp, nowinchk);
}

/* Get Engine Move */

static void getEngmov(BOARD *b, uint32 ldepth)
{
  MOVES  moves;
  int    bub[MAXMV];

  int    m, mm = 0, i, j, v;
  uint32 dm;

  /* setup search moves */

  m = genmoves(b, moves, 0, 1);
  if (m == 0) {
    if (inCheck(b)) {
      fprintf(stdout, "\n\n**** YOU WIN ****\n\n");
    }
    else {
      fprintf(stdout, "\n\n**** STALEMATE ****\n\n");
    }
    return;
  }
  else if (b->r50cnt >= 100) {
    fprintf(stdout, "\n\n**** DRAW BY FIFTY MOVE RULE ****\n\n");
    return;
  }

  /* setup search parameters */

  nodes  = 0;

  /* perform search */

  clock_t time0 = clock();
  double time_taken = 0.0; /* record total time taken */

  for (dm = 1; dm <= ldepth; dm++) {

    int alpha = -32767, beta = 32767;

    curdp = dm;
    seldp = dm;
    extdp = 2 * dm + 2;

    for (i = 0; i < m; i++) {

      uint32 os = b->state, op = b->plycnt, o5 = b->r50cnt;
      uint64 oz = b->zobrist;

      applyMov(b, moves[i], 0);
      v = - searchAB(b, -beta, -alpha, 1, dm, 0, (moves[i] & CHECK), 0);
      bub[i] = v;
      takebMov(b, moves[i], os, op, o5, oz, 0);

      if (v > alpha) {
        alpha = v;
        mm    = i;
      }

    } /* forall moves */

    { uint32 ms = ClockstoMs(clock() - time0);
      double xx = ms / 1000.0;
      double yy = (ms > 0) ? ((double)nodes) / ms : 0.0;
      time_taken = xx;
      showMov(stdout, b, moves[mm]);
      fprintf(stdout, "\tscore=%+4d : moves=%2d :: %4.1lfs %5uKN (%6.1lfKNps) [%2u/%2u]\n",
        (STATE_wtm(b->state)) ? alpha : -alpha, m, xx, nodes/1000, yy, dm, seldp);
    }

    /* full move ordering at the top
     *
     * NOTE: bub[i] contains the alpha-beta score, not the score for just that
     *       move; nevertheless, the sorting tends to move good moves up-front
     */
    for (j = 0; j < m-1; j++) {
      int stable = 1;
      for (i = m-1; j < i; i--) {
        if (bub[i] > bub[i-1]) {
          int tmp1 = bub[i];   bub[i]   = bub[i-1];   bub[i-1]   = tmp1;
          int tmp2 = moves[i]; moves[i] = moves[i-1]; moves[i-1] = tmp2;
          if      (mm == i)   mm--;
          else if (mm == i-1) mm++;
          stable = 0;
        }
      }  /* for i */
      if (stable) break;
    } /* for j */

  } /* for varying depths */

  fprintf(stdout, "best move ");
  showMov(stdout, b, moves[mm]);
  fprintf(stdout, "Total time : %4.1lfs\n", time_taken);
}

/* Parse Forsyth-Edwards Notation (FEN) */

static int parseFen(void)
{
  int done = 0, kk = 91, k = 91, c, c2;

  /* piece placement */
  while (!done) {
    c = fgetc(stdin);
    switch (c) {
      case 'p': interb.board[k++] = BPAWN;   break;
      case 'n': interb.board[k++] = BKNIGHT; break;
      case 'b': interb.board[k++] = BBISHOP; break;
      case 'r': interb.board[k++] = BROOK;   break;
      case 'q': interb.board[k++] = BQUEEN;  break;
      case 'k': interb.bk = k;
                interb.board[k++] = BKING;   break;
      case 'P': interb.board[k++] = WPAWN;   break;
      case 'N': interb.board[k++] = WKNIGHT; break;
      case 'B': interb.board[k++] = WBISHOP; break;
      case 'R': interb.board[k++] = WROOK;   break;
      case 'Q': interb.board[k++] = WQUEEN;  break;
      case 'K': interb.wk = k;
                interb.board[k++] = WKING;   break;
      case '1': k += 1;   break;
      case '2': k += 2;   break;
      case '3': k += 3;   break;
      case '4': k += 4;   break;
      case '5': k += 5;   break;
      case '6': k += 6;   break;
      case '7': k += 7;   break;
      case '8': k += 8;   break;
      case '/': kk -= 10;
                k = kk;   break;
      case '\t':
      case ' ': if (kk != 91) done = 1;
                break;
      default:  return 0; /* unexpected: failure */
    } /* switch */
  }

  /* active color */
  c = fgetc(stdin);
  if (c == 'w') {
    STATE_SET_WTM(interb.state);
  }
  else if (c == 'b') {
    STATE_SET_BTM(interb.state);
  }
  else {
    return 0; /* unexpected: failure */
  }

  c = fgetc(stdin);
  if (c != ' ' && c != 't') {
    return 0; /* unexpected: failure */
  }

  /* castling */
  done = 0;
  while (!done) {
    c = fgetc(stdin);
    switch (c) {
      case 'k': STATE_SET_BCK(interb.state); break;
      case 'q': STATE_SET_BCQ(interb.state); break;
      case 'K': STATE_SET_WCK(interb.state); break;
      case 'Q': STATE_SET_WCQ(interb.state); break;
      case '-':                              break;
      case '\t':
      case ' ': done = 1;                    break;
      default:  return 0; /* unexpected: failure */
    } /* switch */
  }

  /* en passant */
  c = fgetc(stdin);
  switch (c) {
    case 'a':
    case 'b':
    case 'c':
    case 'd':
    case 'e':
    case 'f':
    case 'g':
    case 'h': c2 = fgetc(stdin);
              if (c2 == '3' || c2 == '6') {
                STATE_SET_ENP(interb.state, c-'a');
              }
              else {
                return 0;
              }
              break;
    case '-': break;
    default:  return 0; /* unexpected: failure */
  } /* switch */

  /* moves */
  fscanf(stdin, "%u %u", &interb.r50cnt, &k);

  return 1; /* success */
}

/********************************
 **** Chess Benchmark Driver ****
 ********************************/

int main()
{
  fprintf(stdout, "\nBikJump Benchmark\n");
  fprintf(stdout, "by Aart J.C. Bik\n\n");

  for (int v = 0; v < MAXDP; v++) {
    killerm[v] = 0;
  }

  initZobrist();
  allocTrans(4);

  char token[256];
  int depth;
  while (1) {
    fscanf(stdin, "%255s", token);
    if (strcmp(token, "go"))
      break; // done
    fscanf(stdin, "%d", &depth);
    clearBoard(&interb);
    if (!parseFen()) {
      fprintf(stderr, "fen error\n");
      exit(1);
    }
    interb.zobrist = compZobrist(&interb);
    auxInit(&interb);
    printf("\ngo depth %d\n", depth);
    getEngmov(&interb, depth);
 }

  freeTrans();

  fprintf(stdout, "\nbye!\n\n");
  return 0;
}