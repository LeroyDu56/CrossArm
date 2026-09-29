MODULE PointProbe
    ! CrossArm - point probe: see tools/make_point_probe.py.
    PERS tooldata tProbe:=[TRUE,[[10,-5,120],[1,0,0,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];
    PERS wobjdata wProbe:=[FALSE,TRUE,"",[[1100,-150,650],[0.996195,0,0,0.087156]],[[0,0,0],[1,0,0,0]]];
    CONST robtarget pA:=[[60,20,250],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pB:=[[180,120,250],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pGrid{2,2}:=[[[[40,-40,230],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]],[[100,-40,230],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]]],[[[40,60,230],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]],[[100,60,230],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]]]];

    PROC PointProbe()
        PickAt pA;
        PickAt Offs(pB,0,50,0);
        Twice pB;
        FOR r FROM 1 TO 2 DO
            FOR c FROM 1 TO 2 DO
                MoveL pGrid{r,c},v500,fine,tProbe\WObj:=wProbe;
                PickAt Offs(pGrid{r,c},0,0,20);
            ENDFOR
        ENDFOR
    ENDPROC

    PROC PickAt(robtarget pPick)
        MoveJ Offs(pPick,0,0,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveL pPick,v200,fine,tProbe\WObj:=wProbe;
        MoveL Offs(pPick,10,-20,40),v1000,fine,tProbe\WObj:=wProbe;
    ENDPROC

    PROC Twice(robtarget pTwice)
        PickAt pTwice;
        PickAt Offs(pTwice,30,0,0);
    ENDPROC

    PROC PointDirect()
        MoveJ Offs(pA,0,0,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveL pA,v200,fine,tProbe\WObj:=wProbe;
        MoveL Offs(pA,10,-20,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveJ Offs(Offs(pB,0,50,0),0,0,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveL Offs(pB,0,50,0),v200,fine,tProbe\WObj:=wProbe;
        MoveL Offs(Offs(pB,0,50,0),10,-20,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveJ Offs(pB,0,0,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveL pB,v200,fine,tProbe\WObj:=wProbe;
        MoveL Offs(pB,10,-20,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveJ Offs(Offs(pB,30,0,0),0,0,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveL Offs(pB,30,0,0),v200,fine,tProbe\WObj:=wProbe;
        MoveL Offs(Offs(pB,30,0,0),10,-20,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveL pGrid{1,1},v500,fine,tProbe\WObj:=wProbe;
        MoveJ Offs(Offs(pGrid{1,1},0,0,20),0,0,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveL Offs(pGrid{1,1},0,0,20),v200,fine,tProbe\WObj:=wProbe;
        MoveL Offs(Offs(pGrid{1,1},0,0,20),10,-20,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveL pGrid{1,2},v500,fine,tProbe\WObj:=wProbe;
        MoveJ Offs(Offs(pGrid{1,2},0,0,20),0,0,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveL Offs(pGrid{1,2},0,0,20),v200,fine,tProbe\WObj:=wProbe;
        MoveL Offs(Offs(pGrid{1,2},0,0,20),10,-20,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveL pGrid{2,1},v500,fine,tProbe\WObj:=wProbe;
        MoveJ Offs(Offs(pGrid{2,1},0,0,20),0,0,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveL Offs(pGrid{2,1},0,0,20),v200,fine,tProbe\WObj:=wProbe;
        MoveL Offs(Offs(pGrid{2,1},0,0,20),10,-20,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveL pGrid{2,2},v500,fine,tProbe\WObj:=wProbe;
        MoveJ Offs(Offs(pGrid{2,2},0,0,20),0,0,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveL Offs(pGrid{2,2},0,0,20),v200,fine,tProbe\WObj:=wProbe;
        MoveL Offs(Offs(pGrid{2,2},0,0,20),10,-20,40),v1000,fine,tProbe\WObj:=wProbe;
    ENDPROC
ENDMODULE
