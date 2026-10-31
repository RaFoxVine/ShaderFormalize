struct Packet { uint word; float value; };

Packet SelectPacket(float4 input) {
    uint word = asuint(input.x);
    bool low = word < 0x80000000u;
    Packet selected;
    selected.word = low ? word & 0x00FFFFFFu : word ^ 0x85EBCA6Bu;
    selected.value = low ? input.y : (input.w != input.w ? input.w : input.z);
    Packet copied = selected;
    copied.word = copied.word ^ 0x01010103u;
    return copied;
}

float4 main(float4 input : COLOR0) : SV_Target {
    Packet selected = SelectPacket(input);
    return float4(asfloat(selected.word), selected.value, input.z, input.w);
}
