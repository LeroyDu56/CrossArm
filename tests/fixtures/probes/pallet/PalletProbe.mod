MODULE PalletProbe
    ! CrossArm - pallet probe: see tools/make_pallet_probe.py.
    PERS tooldata tProbe:=[TRUE,[[10,-5,120],[1,0,0,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];
    PERS wobjdata wProbe:=[FALSE,TRUE,"",[[1100,-150,650],[0.996195,0,0,0.087156]],[[0,0,0],[1,0,0,0]]];
    CONST robtarget pOrigin:=[[40,-40,230],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST num LENGTH:=90;
    CONST num WIDTH:=20;
    CONST num HEIGHT:=25;
    CONST num nShift{2}:=[0,30];
    VAR robtarget pPlace;
    VAR robtarget pSeen;

    PROC PalletProbe()
        FOR k FROM 1 TO 2 DO
            FOR c FROM 1 TO 2 DO
                pPlace:=Offs(pOrigin,(c-1)*LENGTH+nShift{k},(k-1)*WIDTH,(k-1)*HEIGHT);
                IF k=2 pPlace:=RelTool(pPlace,0,0,0\Rz:=90);
                MoveL Offs(pPlace,0,0,40),v500,fine,tProbe\WObj:=wProbe;
                MoveL pPlace,v200,fine,tProbe\WObj:=wProbe;
                MoveL Offs(pOrigin,c*LENGTH,k*WIDTH,60),v500,fine,tProbe\WObj:=wProbe;
            ENDFOR
        ENDFOR
        pSeen:=CRobT(\Tool:=tProbe\WObj:=wProbe);
        pSeen.trans.x:=pSeen.trans.x+15;
        MoveL Offs(pSeen,0,10,30),v200,fine,tProbe\WObj:=wProbe;
    ENDPROC

    PROC PalletDirect()
        MoveL Offs(Offs(pOrigin,0,0,0),0,0,40),v500,fine,tProbe\WObj:=wProbe;
        MoveL Offs(pOrigin,0,0,0),v200,fine,tProbe\WObj:=wProbe;
        MoveL Offs(pOrigin,90,20,60),v500,fine,tProbe\WObj:=wProbe;
        MoveL Offs(Offs(pOrigin,90,0,0),0,0,40),v500,fine,tProbe\WObj:=wProbe;
        MoveL Offs(pOrigin,90,0,0),v200,fine,tProbe\WObj:=wProbe;
        MoveL Offs(pOrigin,180,20,60),v500,fine,tProbe\WObj:=wProbe;
        MoveL Offs(RelTool(Offs(pOrigin,30,20,25),0,0,0\Rz:=90),0,0,40),v500,fine,tProbe\WObj:=wProbe;
        MoveL RelTool(Offs(pOrigin,30,20,25),0,0,0\Rz:=90),v200,fine,tProbe\WObj:=wProbe;
        MoveL Offs(pOrigin,90,40,60),v500,fine,tProbe\WObj:=wProbe;
        MoveL Offs(RelTool(Offs(pOrigin,120,20,25),0,0,0\Rz:=90),0,0,40),v500,fine,tProbe\WObj:=wProbe;
        MoveL RelTool(Offs(pOrigin,120,20,25),0,0,0\Rz:=90),v200,fine,tProbe\WObj:=wProbe;
        MoveL Offs(pOrigin,180,40,60),v500,fine,tProbe\WObj:=wProbe;
        MoveL Offs(Offs(Offs(pOrigin,180,40,60),15,0,0),0,10,30),v200,fine,tProbe\WObj:=wProbe;
    ENDPROC
ENDMODULE
