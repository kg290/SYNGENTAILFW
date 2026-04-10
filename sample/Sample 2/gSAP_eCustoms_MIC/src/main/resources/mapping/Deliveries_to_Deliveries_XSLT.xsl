<?xml version="1.0"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
    <xsl:output method="xml" indent="no"/>
    <xsl:strip-space elements="*"/>

    <!-- Template to match the root and apply templates to all child elements -->
    <xsl:template match="/">
        <xsl:apply-templates/>
    </xsl:template>

    <!-- Template to match all elements -->
    <xsl:template match="*">
        <!-- Check if the element is not empty or contains non-whitespace text -->
        <xsl:if test="normalize-space(.) != ''">
            <xsl:copy>
                <!-- Copy all attributes of the element -->
                <xsl:copy-of select="@*"/>
                <!-- Apply templates to child elements -->
                <xsl:apply-templates/>
            </xsl:copy>
        </xsl:if>
    </xsl:template>
</xsl:stylesheet>









<!--<?xml version="1.0"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
version="1.0">
<xsl:output method="xml"/>

<xsl:template match="/">
	<xsl:apply-templates select="*"/>
</xsl:template>

<xsl:template match="*">
	<xsl:if test=". != ''">
		<xsl:copy>
			
				<xsl:copy-of select="@*"/>
				<xsl:apply-templates/>
			
		</xsl:copy>
	</xsl:if>
</xsl:template>

</xsl:stylesheet>-->
