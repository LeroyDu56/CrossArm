MODULE PointProbe
    ! CrossArm - point probe: see tools/make_point_probe.py.
    PERS tooldata tProbe:=[TRUE,[[10,-5,120],[1,0,0,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];
    PERS wobjdata wProbe:=[FALSE,TRUE,"",[[1100,-150,650],[0.996195,0,0,0.087156]],[[0,0,0],[1,0,0,0]]];
    PERS tooldata tProbe2:=[TRUE,[[25,10,140],[0.9914449,0,0,0.1305262]],[1,[0,0,50],[1,0,0,0],0,0,0]];
    PERS wobjdata wProbe2:=[FALSE,TRUE,"",[[1150,-100,600],[0.9961947,0,0,-0.0871557]],[[0,0,0],[1,0,0,0]]];
    CONST robtarget pOwn:=[[120,40,240],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pA:=[[60,20,250],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pB:=[[180,120,250],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pGrid{2,2}:=[[[[40,-40,230],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]],[[100,-40,230],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]]],[[[40,60,230],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]],[[100,60,230],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]]]];

    PROC PointProbe()
        PickAt pA;
        PickAt Offs(pB,0,50,0);
        Twice pB;
        Turn pA;
        Lift pB,25;
        WithTool pA,tProbe2\WObj:=wProbe2;
        WithTool Offs(pB,0,0,10),tProbe\WObj:=wProbe;
        FOR r FROM 1 TO 2 DO
            FOR c FROM 1 TO 2 DO
                MoveL pGrid{r,c},v500,fine,tProbe\WObj:=wProbe;
                PickAt Offs(pGrid{r,c},0,0,20);
                MoveL RelTool(pGrid{r,c},5,0,-15\Rz:=20),v500,fine,tProbe\WObj:=wProbe;
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

    PROC Turn(robtarget pTurn)
        MoveL RelTool(pTurn,0,0,-30),v200,fine,tProbe\WObj:=wProbe;
        MoveL RelTool(pTurn,10,-5,-20\Rz:=30),v200,fine,tProbe\WObj:=wProbe;
        MoveJ RelTool(pTurn,0,0,-20\Rx:=8\Ry:=-6\Rz:=15),v1000,fine,tProbe\WObj:=wProbe;
    ENDPROC

    PROC Lift(robtarget pLift,num nUp)
        MoveL RelTool(pLift,0,0,-nUp),v200,fine,tProbe\WObj:=wProbe;
        MoveL Offs(pLift,5,0,-nUp),v200,fine,tProbe\WObj:=wProbe;
    ENDPROC

    PROC WithTool(robtarget pWith,PERS tooldata tWith\PERS wobjdata WObj)
        MoveJ Offs(pWith,0,0,40),v1000,fine,tWith\WObj?WObj;
        MoveL pWith,v200,fine,tWith\WObj?WObj;
        MoveL pOwn,v200,fine,tWith\WObj?WObj;
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
        MoveL RelTool(pA,0,0,-30),v200,fine,tProbe\WObj:=wProbe;
        MoveL RelTool(pA,10,-5,-20\Rz:=30),v200,fine,tProbe\WObj:=wProbe;
        MoveJ RelTool(pA,0,0,-20\Rx:=8\Ry:=-6\Rz:=15),v1000,fine,tProbe\WObj:=wProbe;
        MoveL RelTool(pB,0,0,-25),v200,fine,tProbe\WObj:=wProbe;
        MoveL Offs(pB,5,0,-25),v200,fine,tProbe\WObj:=wProbe;
        MoveJ Offs(pA,0,0,40),v1000,fine,tProbe2\WObj:=wProbe2;
        MoveL pA,v200,fine,tProbe2\WObj:=wProbe2;
        MoveL pOwn,v200,fine,tProbe2\WObj:=wProbe2;
        MoveJ Offs(Offs(pB,0,0,10),0,0,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveL Offs(pB,0,0,10),v200,fine,tProbe\WObj:=wProbe;
        MoveL pOwn,v200,fine,tProbe\WObj:=wProbe;
        MoveL pGrid{1,1},v500,fine,tProbe\WObj:=wProbe;
        MoveJ Offs(Offs(pGrid{1,1},0,0,20),0,0,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveL Offs(pGrid{1,1},0,0,20),v200,fine,tProbe\WObj:=wProbe;
        MoveL Offs(Offs(pGrid{1,1},0,0,20),10,-20,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveL RelTool(pGrid{1,1},5,0,-15\Rz:=20),v500,fine,tProbe\WObj:=wProbe;
        MoveL pGrid{1,2},v500,fine,tProbe\WObj:=wProbe;
        MoveJ Offs(Offs(pGrid{1,2},0,0,20),0,0,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveL Offs(pGrid{1,2},0,0,20),v200,fine,tProbe\WObj:=wProbe;
        MoveL Offs(Offs(pGrid{1,2},0,0,20),10,-20,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveL RelTool(pGrid{1,2},5,0,-15\Rz:=20),v500,fine,tProbe\WObj:=wProbe;
        MoveL pGrid{2,1},v500,fine,tProbe\WObj:=wProbe;
        MoveJ Offs(Offs(pGrid{2,1},0,0,20),0,0,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveL Offs(pGrid{2,1},0,0,20),v200,fine,tProbe\WObj:=wProbe;
        MoveL Offs(Offs(pGrid{2,1},0,0,20),10,-20,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveL RelTool(pGrid{2,1},5,0,-15\Rz:=20),v500,fine,tProbe\WObj:=wProbe;
        MoveL pGrid{2,2},v500,fine,tProbe\WObj:=wProbe;
        MoveJ Offs(Offs(pGrid{2,2},0,0,20),0,0,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveL Offs(pGrid{2,2},0,0,20),v200,fine,tProbe\WObj:=wProbe;
        MoveL Offs(Offs(pGrid{2,2},0,0,20),10,-20,40),v1000,fine,tProbe\WObj:=wProbe;
        MoveL RelTool(pGrid{2,2},5,0,-15\Rz:=20),v500,fine,tProbe\WObj:=wProbe;
    ENDPROC
ENDMODULE
