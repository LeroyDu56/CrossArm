MODULE FuncTextProbe
    ! CrossArm - text FUNC probe: see tools/make_func_text_probe.py.
    VAR string ftCode;
    VAR string ftTag;
    VAR string ftLong;
    VAR num ftPart:=0;
    VAR num ftHits:=0;
    VAR num ftLen1:=0;
    VAR num ftLen2:=0;
    VAR num ftLen3:=0;
    VAR num ftLen4:=0;
    VAR num ftDone:=0;

    PROC FtProbe()
        ftDone:=0;
        ftHits:=0;
        ftPart:=0;
        FOR k FROM 1 TO 3 DO
            ftPart:=ftPart+7;
            ftCode:=FtPad(NumToStr(ftPart,0),5\Fill:="0");
            IF ftCode="00007" ftHits:=ftHits+1;
            IF ftCode="00021" ftHits:=ftHits+100;
        ENDFOR
        ftLen1:=StrLen(ftCode);
        ftTag:="#"+FtPad(NumToStr(ftPart,0),4)+"-"+FtJoin(ftCode,"9");
        ftLen2:=StrLen(ftTag);
        IF ftTag="#  21-00021/9" ftHits:=ftHits+10;
        ftLong:=FtJoin(FtJoin(ftTag,ftTag),FtRepeat("12345",10));
        ftLen3:=StrLen(ftLong);
        ftLen4:=StrLen(FtPad("",3));
        IF FtPad("12",2)="12" ftHits:=ftHits+1000;
        ftDone:=1;
    ENDPROC

    FUNC string FtPad(string text,num width,\string Fill)
        VAR string padded;
        VAR string pad:=" ";
        IF StrLen(text)>=width THEN
            RETURN text;
        ENDIF
        IF Present(Fill) pad:=Fill;
        padded:=text;
        FOR i FROM StrLen(text) TO width-1 DO
            padded:=pad+padded;
        ENDFOR
        RETURN padded;
    ENDFUNC

    FUNC string FtJoin(string first,string second)
        RETURN first+"/"+second;
    ENDFUNC

    FUNC string FtRepeat(string text,num times)
        VAR string all;
        FOR i FROM 1 TO times DO
            all:=all+text;
        ENDFOR
        RETURN all;
    ENDFUNC
ENDMODULE
