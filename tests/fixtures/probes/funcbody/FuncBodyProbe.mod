MODULE FuncBodyProbe
    ! CrossArm - FUNC body probe: see tools/make_func_body_probe.py.
    CONST robtarget fbOrigin:=[[1000,-100,800],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    VAR robtarget fbP;
    VAR robtarget fbW;
    VAR bool fbB:=FALSE;
    VAR num fbSum:=0;
    VAR num fbFlags:=0;
    VAR num fbLoops:=0;
    VAR num fbCount:=0;
    VAR num fbNest:=0;
    VAR num fbBias:=0;
    VAR num fbX:=0;
    VAR num fbY:=0;
    VAR num fbZ:=0;
    VAR num fbX1:=0;
    VAR num fbY1:=0;
    VAR num fbBack:=0;
    VAR num fbDone:=0;

    PROC FbProbe()
        fbDone:=0;
        fbSum:=0;
        fbFlags:=0;
        fbLoops:=0;
        fbCount:=0;
        fbBack:=0;
        fbBias:=0.5;
        FOR i FROM 1 TO 4 DO
            fbSum:=fbSum+FbScale(i)*10;
            IF FbEven(i) THEN
                fbFlags:=fbFlags+1;
            ELSEIF FbBig(i) THEN
                fbFlags:=fbFlags+100;
            ENDIF
        ENDFOR
        WHILE NOT FbDone() DO
            fbLoops:=fbLoops+1;
        ENDWHILE
        fbNest:=FbScale(fbLoops)+FbOuter(3);
        fbP:=FbCell(fbLoops,3);
        MoveJ fbP,v500,fine,tool0;
        fbX:=fbP.trans.x;
        fbY:=fbP.trans.y;
        fbZ:=fbP.trans.z;
        MoveL FbCell(1,1),v500,fine,tool0;
        fbW:=CRobT(\Tool:=tool0\WObj:=wobj0);
        fbX1:=fbW.trans.x;
        fbY1:=fbW.trans.y;
        fbB:=FbBig(1);
        IF fbB THEN
            fbBack:=1;
        ELSE
            fbBack:=2;
        ENDIF
        IF NOT FbEven(2) THEN
            fbBack:=fbBack+10;
        ENDIF
        IF NOT FbEven(fbBack+1) THEN
            fbBack:=fbBack+100;
        ENDIF
        fbDone:=1;
    ENDPROC

    FUNC num FbScale(num k)
        VAR num r;
        r:=k*k;
        IF r>5 THEN
            RETURN r-1;
        ENDIF
        RETURN r+fbBias;
    ENDFUNC

    FUNC bool FbEven(num k)
        IF k MOD 2=0 THEN
            RETURN TRUE;
        ENDIF
        RETURN FALSE;
    ENDFUNC

    FUNC bool FbBig(num k)
        IF k>2 THEN
            RETURN TRUE;
        ENDIF
        RETURN FALSE;
    ENDFUNC

    FUNC bool FbDone()
        fbCount:=fbCount+1;
        RETURN fbCount>=3;
    ENDFUNC

    FUNC num FbOuter(num k)
        VAR num a;
        a:=FbScale(k);
        RETURN a+FbScale(k+1);
    ENDFUNC

    FUNC robtarget FbCell(num row,num col)
        VAR robtarget p;
        p:=fbOrigin;
        p.trans.x:=fbOrigin.trans.x+(col-1)*20;
        p.trans.y:=fbOrigin.trans.y+(row-1)*30;
        RETURN p;
    ENDFUNC
ENDMODULE
